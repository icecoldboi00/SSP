# managers/ink_analysis_manager.py

import fitz  # PyMuPDF
import numpy as np
from datetime import datetime

class InkAnalysisManager:
    """Manages ink usage analysis for PDF files and updates database accordingly."""
    
    # Standard coverage percentage for a single channel (C, M, Y, or K) on a "standard page".
    # Industry standard for ISO yield tests is often around 5% per channel.
    STANDARD_CHANNEL_COVERAGE_PERCENT = 5.0
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        # Track which cartridges have already sent low ink alerts
        self.low_ink_alerts_sent = {
            'cyan': False,
            'magenta': False, 
            'yellow': False,
            'black': False
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
        """
        Calculates the percentage of each individual cartridge used for a print job.
        """
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
    
    def _create_error_result(self, error_message):
        """Create an error result."""
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
    
    def update_database_after_print(self, analysis_result, copies=1, color_mode="Color"):      
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
            
            # Print deducted amounts
            print(f"Ink Deducted - C: {deducted_cyan:.2f}%, M: {deducted_magenta:.2f}%, Y: {deducted_yellow:.2f}%, K: {deducted_black:.2f}%")
            
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
    
    def analyze_and_update_after_print(self, pdf_path, selected_pages=None, copies=1, dpi=150, color_mode="Color"):
        # Analyze the PDF
        analysis_result = self.analyze_pdf_ink_usage(pdf_path, selected_pages, dpi)
        
        if not analysis_result.get('success', False):
            return analysis_result
        
        # Update database
        update_success = self.update_database_after_print(analysis_result, copies, color_mode)
        
        analysis_result['database_updated'] = update_success
        
        # Check for low ink levels and send SMS alerts if needed
        if update_success:
            self._check_and_send_low_ink_alerts()
        
        return analysis_result
    
    def _check_and_send_low_ink_alerts(self):
        """Check current ink levels and send SMS alerts for cartridges below 20%."""
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
            
            # Send SMS alerts if any cartridges are low
            if low_cartridges:
                try:
                    from managers.sms_manager import send_multiple_low_ink_sms
                    if len(low_cartridges) == 1:
                        # Single cartridge low
                        cartridge_name, level = low_cartridges[0]
                        from managers.sms_manager import send_low_ink_sms
                        send_low_ink_sms(cartridge_name, level)
                        print(f"SMS alert sent for low {cartridge_name} ink ({level:.1f}%)")
                    else:
                        # Multiple cartridges low
                        send_multiple_low_ink_sms(low_cartridges)
                        print(f"SMS alert sent for {len(low_cartridges)} low ink cartridges")
                except Exception as e:
                    print(f"Error sending low ink SMS alert: {e}")
            else:
                print("All ink levels are above 20% threshold")
                
        except Exception as e:
            print(f"Error checking ink levels for SMS alerts: {e}")
    
    def reset_low_ink_alerts(self):
        """Reset all low ink alert flags (call this when cartridges are refilled)."""
        self.low_ink_alerts_sent = {
            'cyan': False,
            'magenta': False,
            'yellow': False,
            'black': False
        }
        print("Low ink alert flags reset - cartridges refilled")
