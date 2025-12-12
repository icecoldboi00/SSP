import fitz
import numpy as np
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from database.db_manager import DatabaseManager


class InkAnalysisThread(QThread):
    analysis_completed = pyqtSignal(dict)
    database_updated = pyqtSignal(bool)
    
    def __init__(self, pdf_path, selected_pages=None, copies=1, dpi=150):
        super().__init__()
        self.pdf_path = pdf_path
        self.selected_pages = selected_pages
        self.copies = copies
        self.dpi = dpi
        
        # Create managers in this thread (in run method)
        self.db_manager = None
        self.ink_analysis_manager = None
    
    def run(self):
        try:
            # Create managers in this thread
            self.db_manager = DatabaseManager()
            self.ink_analysis_manager = InkAnalysisManager(self.db_manager)
            
            # Perform analysis and update database
            result = self.ink_analysis_manager.analyze_and_update_after_print(
                pdf_path=self.pdf_path,
                selected_pages=self.selected_pages,
                copies=self.copies,
                dpi=self.dpi
            )
            
            # Safety check: ensure result is valid
            if not result or not isinstance(result, dict):
                print("Invalid result from ink analysis")
                self.database_updated.emit(False)
                return
            
            # Emit results
            self.analysis_completed.emit(result)
            
            # Emit database update status and updated CMYK levels
            if result.get('database_updated', False):
                self.database_updated.emit(True)
                
                # Get and emit updated CMYK levels
                updated_levels = self.db_manager.get_cmyk_ink_levels()
                if updated_levels:
                    self.analysis_completed.emit({
                        'success': True,
                        'database_updated': True,
                        'cmyk_levels': updated_levels
                    })
            else:
                self.database_updated.emit(False)
                
        except Exception as e:
            print(f"Error in ink analysis: {e}")
            self.database_updated.emit(False)
            
            # Log error to database
            try:
                from utils.error_logger import log_error
                log_error("Ink Analysis Error", str(e), "ink_analysis_manager")
            except Exception as db_error:
                print(f"Failed to log error to database: {db_error}")
        finally:
            # Cleanup database connection
            if self.db_manager:
                self.db_manager.close()


class InkAnalysisManager:
    # Standard coverage percentage for a single channel (C, M, Y, or K) on a "standard page".
    # Industry standard for ISO yield tests is often around 5% per channel.
    STANDARD_CHANNEL_COVERAGE_PERCENT = 5.0
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        # Track which cartridges have already sent low ink alerts
        self.low_ink_alerts_sent = {
            'cyan': False,
            'magenta': False, 
            'yellow': False,
            'black': False
        }
        # Track coin low alerts to avoid spamming until refilled
        self.low_coin_alerts_sent = {
            'peso_1': False,
            'peso_5': False
        }
        
    def analyze_pdf_ink_usage(self, pdf_path, selected_pages=None, dpi=150):
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if total_pages == 0:
                doc.close()
                return self._create_empty_result()
            
            # Filter to selected pages if specified
            if selected_pages:
                # Convert to 0-indexed and filter
                pages_to_analyze = [i-1 for i in selected_pages if 1 <= i <= total_pages]
            else:
                pages_to_analyze = list(range(total_pages))
            
            if not pages_to_analyze:
                doc.close()
                return self._create_empty_result()
            
            # Analyze each page
            total_c, total_m, total_y, total_k = 0, 0, 0, 0
            analyzed_pages = 0
            
            for page_num in pages_to_analyze:
                page = doc[page_num]
                # Render page in CMYK colorspace
                pix = page.get_pixmap(colorspace=fitz.csCMYK, dpi=dpi)
                
                # Analyze ink usage for this page
                c, m, y, k = self._analyze_page_coverage_fitz(pix)
                
                total_c += c
                total_m += m
                total_y += y
                total_k += k
                analyzed_pages += 1
            
            doc.close()
            
            # Calculate averages
            avg_c = total_c / analyzed_pages
            avg_m = total_m / analyzed_pages
            avg_y = total_y / analyzed_pages
            avg_k = total_k / analyzed_pages
            
            # Calculate job costs (percentage of cartridge used)
            job_costs_dict = self._calculate_job_costs(
                avg_k, avg_c, avg_m, avg_y, analyzed_pages
            )
            
            # Print ink usage percentages
            print(f"Ink Usage - C: {job_costs_dict['cyan']:.2f}%, M: {job_costs_dict['magenta']:.2f}%, Y: {job_costs_dict['yellow']:.2f}%, K: {job_costs_dict['black']:.2f}%")
            
            result = {
                'success': True,
                'total_pages': total_pages,
                'analyzed_pages': analyzed_pages,
                'selected_pages': selected_pages,
                'averages': {
                    'cyan': avg_c,
                    'magenta': avg_m,
                    'yellow': avg_y,
                    'black': avg_k
                },
                'totals': {
                    'cyan': total_c,
                    'magenta': total_m,
                    'yellow': total_y,
                    'black': total_k
                },
                'job_costs': job_costs_dict, # Assign the entire dictionary here
                'timestamp': datetime.now()
            }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing PDF ink usage: {e}")
            import traceback
            traceback.print_exc()
            return self._create_error_result(str(e))
    
    def _analyze_page_coverage_fitz(self, pix):
        if pix.width == 0 or pix.height == 0:
            return 0, 0, 0, 0
        
        # Max possible ink value for one channel on this page (every pixel = 255)
        max_channel_value = np.uint64(pix.width) * np.uint64(pix.height) * 255
        
        if max_channel_value == 0:
            return 0, 0, 0, 0

        # Get the raw C,M,Y,K byte data and use numpy for super-fast summing
        samples = np.frombuffer(pix.samples, dtype=np.uint8).reshape(-1, 4)
        cmyk_totals = samples.sum(axis=0, dtype=np.uint64)

        # Calculate the percentage of coverage for each channel on this page
        cyan_coverage = (cmyk_totals[0] / max_channel_value) * 100
        magenta_coverage = (cmyk_totals[1] / max_channel_value) * 100
        yellow_coverage = (cmyk_totals[2] / max_channel_value) * 100
        black_coverage = (cmyk_totals[3] / max_channel_value) * 100
        
        return cyan_coverage, magenta_coverage, yellow_coverage, black_coverage
    
    def _calculate_channel_cost(self, avg_coverage_percent, total_pages_in_job, yield_pages_for_cartridge, standard_coverage_percent):
        if yield_pages_for_cartridge <= 0 or standard_coverage_percent <= 0:
            return 0.0 # Avoid division by zero, or if cartridge has no yield

        if avg_coverage_percent <= 0:
            return 0.0 # If the job uses no ink for this channel, cost is 0

        # How many "standard pages" one physical page of *this job* is equivalent to.
        # E.g., if avg_coverage is 10% and standard is 5%, then 1 real page = 2 standard pages.
        equivalent_standard_pages_per_real_page = avg_coverage_percent / standard_coverage_percent

        # Total equivalent standard pages for this entire job for this channel
        total_equivalent_standard_pages_for_job = total_pages_in_job * equivalent_standard_pages_per_real_page

        # Percentage of cartridge used
        cartridge_used_percent = (total_equivalent_standard_pages_for_job / yield_pages_for_cartridge) * 100
        
        return cartridge_used_percent

    def _calculate_job_costs(self, avg_k, avg_c, avg_m, avg_y, total_pages, 
                           yield_black=7000, yield_color=7000, standard_coverage=5.0):
        # Calculate individual channel costs
        c_cost = self._calculate_channel_cost(avg_c, total_pages, yield_color, self.STANDARD_CHANNEL_COVERAGE_PERCENT)
        m_cost = self._calculate_channel_cost(avg_m, total_pages, yield_color, self.STANDARD_CHANNEL_COVERAGE_PERCENT)
        y_cost = self._calculate_channel_cost(avg_y, total_pages, yield_color, self.STANDARD_CHANNEL_COVERAGE_PERCENT)
        k_cost = self._calculate_channel_cost(avg_k, total_pages, yield_black, self.STANDARD_CHANNEL_COVERAGE_PERCENT)
        
        # Return a dictionary with the cost for each separate cartridge
        return {
            'cyan': c_cost,
            'magenta': m_cost,
            'yellow': y_cost,
            'black': k_cost
        }
    # Added here just to avoid errors
    def _create_empty_result(self):
        return {
            'success': True,
            'total_pages': 0,
            'analyzed_pages': 0,
            'selected_pages': None,
            'averages': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'totals': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'job_costs': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'timestamp': datetime.now()
        }
    # Added here just to avoid errors
    def _create_error_result(self, error_message):
        return {
            'success': False,
            'error': error_message,
            'total_pages': 0,
            'analyzed_pages': 0,
            'selected_pages': None,
            'averages': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'totals': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'job_costs': {'cyan': 0, 'magenta': 0, 'yellow': 0, 'black': 0},
            'timestamp': datetime.now()
        }
    
    def update_database_after_print(self, analysis_result, copies=1):      
        if not self.db_manager:
            print("Warning: No database manager provided, cannot update ink levels")
            return False
        
        if not analysis_result.get('success', False):
            print("Warning: Analysis failed, cannot update ink levels")
            return False
        
        try:
            # Get current ink levels
            current_levels = self.db_manager.get_cmyk_ink_levels()
            
            if not current_levels:
                print("Warning: No current ink levels found, cannot update")
                return False
            
            # Calculate ink usage for all copies
            job_costs = analysis_result['job_costs']
            copies_factor = copies
            
            # Deduct actual ink usage from all cartridges regardless of color mode
            deducted_cyan = job_costs['cyan'] * copies_factor
            deducted_magenta = job_costs['magenta'] * copies_factor
            deducted_yellow = job_costs['yellow'] * copies_factor
            deducted_black = job_costs['black'] * copies_factor
            
            new_cyan = max(0, current_levels['cyan'] - deducted_cyan)
            new_magenta = max(0, current_levels['magenta'] - deducted_magenta)
            new_yellow = max(0, current_levels['yellow'] - deducted_yellow)
            new_black = max(0, current_levels['black'] - deducted_black)
            
            # Update database
            success = self.db_manager.update_cmyk_ink_levels(
                new_cyan, new_magenta, new_yellow, new_black
            )
            
            if success:
                return True
            else:
                print("Error: Failed to update ink levels in database")
                return False
                
        except Exception as e:
            print(f"Error updating ink levels after printing: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def analyze_and_update_after_print(self, pdf_path, selected_pages=None, copies=1, dpi=150):
        # Analyze the PDF
        analysis_result = self.analyze_pdf_ink_usage(pdf_path, selected_pages, dpi)
        
        if not analysis_result.get('success', False):
            return analysis_result
        
        # Determine if copies are already duplicated in the temp PDF
        # Single page + multiple copies: temp PDF has 1 page, CUPS handles copies → multiply by copies
        # Multi-page: temp PDF has pages × copies → don't multiply (already included)
        analyzed_pages = analysis_result.get('analyzed_pages', 0)
        if analyzed_pages == 1 and copies > 1:
            # Single page with multiple copies: temp PDF has 1 page, need to multiply
            copies_factor = copies
            print(f"Single page with {copies} copies: multiplying ink usage by {copies}")
        else:
            # Multi-page or single copy: temp PDF already has all copies, don't multiply
            copies_factor = 1
            print(f"Temp PDF has {analyzed_pages} pages: copies already included, not multiplying")
        
        # Update database
        update_success = self.update_database_after_print(analysis_result, copies_factor)
        
        analysis_result['database_updated'] = update_success
        
        # Check for low ink levels and send SMS alerts if needed
        if update_success:
            self._check_and_send_low_ink_alerts()
            # Also check coin levels after ink check
            self._check_and_send_low_coin_alerts()
        
        return analysis_result
    
    def _check_and_send_low_ink_alerts(self):
        try:
            # Get current ink levels
            current_levels = self.db_manager.get_cmyk_ink_levels()
            if not current_levels:
                print("Warning: No current ink levels found for monitoring")
                return
            
            low_ink_threshold = 20.0
            low_cartridges = []
            
            # Check each cartridge
            cartridges = {
                'cyan': current_levels['cyan'],
                'magenta': current_levels['magenta'],
                'yellow': current_levels['yellow'],
                'black': current_levels['black']
            }
            
            for cartridge_name, level in cartridges.items():
                if level <= low_ink_threshold:
                    # Check if we haven't already sent an alert for this cartridge
                    if not self.low_ink_alerts_sent[cartridge_name]:
                        low_cartridges.append((cartridge_name.capitalize(), level))
                        self.low_ink_alerts_sent[cartridge_name] = True
                        print(f"Low ink alert flag set for {cartridge_name} ({level:.1f}%)")
                else:
                    # Reset alert flag if cartridge is above threshold (refilled)
                    if self.low_ink_alerts_sent[cartridge_name]:
                        self.low_ink_alerts_sent[cartridge_name] = False
                        print(f"Low ink alert flag reset for {cartridge_name} ({level:.1f}%) - cartridge refilled")
            
            # Send SMS alerts and log to database if any cartridges are low
            if low_cartridges:
                try:
                    from managers.sms_manager import send_multiple_low_ink_sms
                    if len(low_cartridges) == 1:
                        # Single cartridge low
                        cartridge_name, level = low_cartridges[0]
                        from managers.sms_manager import send_low_ink_sms
                        send_low_ink_sms(cartridge_name, level)
                        print(f"SMS alert sent for low {cartridge_name} ink ({level:.1f}%)")
                        
                        # Log to error database
                        try:
                            from utils.error_logger import log_error
                            log_error("Low Ink", f"{cartridge_name} ink is low ({level:.1f}%)", "ink_analysis_manager")
                        except Exception as log_err:
                            print(f"Failed to log low ink error to database: {log_err}")
                    else:
                        # Multiple cartridges low
                        send_multiple_low_ink_sms(low_cartridges)
                        print(f"SMS alert sent for {len(low_cartridges)} low ink cartridges")
                        
                        # Log to error database
                        try:
                            from utils.error_logger import log_error
                            cartridge_list = ", ".join([f"{name} ({level:.1f}%)" for name, level in low_cartridges])
                            log_error("Low Ink", f"Multiple ink cartridges are low: {cartridge_list}", "ink_analysis_manager")
                        except Exception as log_err:
                            print(f"Failed to log low ink error to database: {log_err}")
                except Exception as e:
                    print(f"Error sending low ink SMS alert: {e}")
            else:
                print("All ink levels are above 20% threshold")
                
        except Exception as e:
            print(f"Error checking ink levels for SMS alerts: {e}")
    
    def reset_low_ink_alerts(self):
        self.low_ink_alerts_sent = {
            'cyan': False,
            'magenta': False,
            'yellow': False,
            'black': False
        }
        print("Low ink flags reset")
    
    # Added instead of checking in thank you screen to avoid spamming
    def _check_and_send_low_coin_alerts(self):
        try:
            # Get current coin counts from database
            inventory = self.db_manager.get_cash_inventory()
            coin_1_count = 0
            coin_5_count = 0
            
            for item in inventory:
                if item['denomination'] == 1 and item['type'] == 'coin':
                    coin_1_count = item['count']
                elif item['denomination'] == 5 and item['type'] == 'coin':
                    coin_5_count = item['count']
            
            low_coin_thresholds = {'peso_1': 5, 'peso_5': 3}  # Your specified thresholds
            low_coins = []
            
            # Check ₱1 coins
            if coin_1_count <= low_coin_thresholds['peso_1']:
                # Only alert if not already sent
                if not self.low_coin_alerts_sent['peso_1']:
                    low_coins.append(('1-peso', coin_1_count))
                    self.low_coin_alerts_sent['peso_1'] = True
                    print(f"Low 1-peso coins alert flagged ({coin_1_count} remaining)")
            else:
                # Reset flag if refilled above threshold
                if self.low_coin_alerts_sent['peso_1']:
                    self.low_coin_alerts_sent['peso_1'] = False
                    print("1-peso coin alert flag reset (refilled)")
            
            # Check ₱5 coins
            if coin_5_count <= low_coin_thresholds['peso_5']:
                if not self.low_coin_alerts_sent['peso_5']:
                    low_coins.append(('5-peso', coin_5_count))
                    self.low_coin_alerts_sent['peso_5'] = True
                    print(f"Low 5-peso coins alert flagged ({coin_5_count} remaining)")
            else:
                if self.low_coin_alerts_sent['peso_5']:
                    self.low_coin_alerts_sent['peso_5'] = False
                    print("5-peso coin alert flag reset (refilled)")
            
            # Send SMS alerts if any coins are low
            if low_coins:
                try:
                    from managers.sms_manager import send_multiple_low_coins_sms, send_low_coin_sms
                    if len(low_coins) == 1:
                        # Single coin type low
                        coin_type, count = low_coins[0]
                        send_low_coin_sms(coin_type, count)
                        print(f"SMS alert sent for low {coin_type} coins ({count} remaining)")
                    else:
                        # Multiple coin types low
                        send_multiple_low_coins_sms(low_coins)
                        print(f"SMS alert sent for {len(low_coins)} low coin types")
                except Exception as e:
                    print(f"Error sending low coin SMS alert: {e}")
            else:
                print("All coin levels are above threshold")
                
        except Exception as e:
            print(f"Error checking coin levels for SMS alerts: {e}")
