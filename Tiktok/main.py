import time
import random
import json
import requests
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from colorama import init, Fore

init(autoreset=True)

class Bot:
    def __init__(self):
        self.clear_screen()
        self.proxies = []
        self.current_proxy_index = 0
        self.load_proxies()
        self.setup_service_xpaths()
        self.service_wait_times = { # Custom wait times for each service with bounds
            "followers": (125, 135),
            "hearts": (125, 135),
            "comment_hearts": (125, 135),
            "views": (125, 135),
            "shares": (85, 100),
            "favorites": (125, 135),
        }
        self.log_lock = threading.Lock()  # Lock for thread-safe logging
        self.url_queue = queue.Queue()  # Queue for URLs to process
        self.result_queue = queue.Queue()  # Queue for results
        self.stop_event = threading.Event()  # Event to signal threads to stop
        self.max_threads = 1  # Default to 1 thread

    def log(self, message, color=Fore.WHITE):
        """Thread-safe logging"""
        with self.log_lock:
            print(color + message)

    def clear_screen(self): # Escape sequence to clear the screen
        print("\033c", end="")
        
    def load_proxies(self):
        """Load proxies from file or prompt user to enter them"""
        try:
            with open("proxies.txt", "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
                if proxies:
                    self.proxies = proxies
                    print(Fore.GREEN + f"[+] Loaded {len(proxies)} proxies from file")
                    return
        except FileNotFoundError:
            pass
            
        print(Fore.YELLOW + "[~] No proxy file found or file is empty")
        choice = input(Fore.YELLOW + "[-] Do you want to: (1) Enter proxies manually (2) Continue without proxies: ")
        
        if choice == "1":
            print(Fore.CYAN + "[-] Enter your proxies one per line (format: ip:port or user:pass@ip:port)")
            print(Fore.CYAN + "[-] Enter an empty line when finished")
            
            while True:
                proxy = input().strip()
                if not proxy:
                    break
                self.proxies.append(proxy)
                
            # Save proxies to file for future use
            if self.proxies:
                with open("proxies.txt", "w") as f:
                    f.write("\n".join(self.proxies))
                print(Fore.GREEN + f"[+] Saved {len(self.proxies)} proxies to proxies.txt")
                
    def test_proxy(self, proxy):
        """Test if a proxy is working"""
        try:
            proxy_dict = self.format_proxy_for_requests(proxy)
            test_url = "https://www.google.com"
            response = requests.get(test_url, proxies=proxy_dict, timeout=10)
            return response.status_code == 200
        except Exception as e:
            return False
            
    def format_proxy_for_requests(self, proxy):
        """Format proxy for requests library"""
        if '@' in proxy:  # proxy with authentication
            protocol = "http://"
            return {"http": protocol + proxy, "https": protocol + proxy}
        else:  # proxy without authentication
            protocol = "http://"
            return {"http": protocol + proxy, "https": protocol + proxy}
            
    def format_proxy_for_selenium(self, proxy):
        """Format proxy string for selenium"""
        if '@' in proxy:  # proxy with authentication
            auth, ip_port = proxy.split('@')
            username, password = auth.split(':')
            return {
                "proxyType": "manual",
                "httpProxy": ip_port,
                "sslProxy": ip_port,
                "socksUsername": username,
                "socksPassword": password
            }
        else:  # proxy without authentication
            return {
                "proxyType": "manual",
                "httpProxy": proxy,
                "sslProxy": proxy
            }

    def get_working_proxy(self):
        """Get a working proxy from the list"""
        if not self.proxies:
            return None
            
        # Create a local copy and shuffle to randomize selection
        available_proxies = self.proxies.copy()
        random.shuffle(available_proxies)
        
        for proxy in available_proxies:
            self.log(f"[~] Testing proxy: {proxy}", Fore.YELLOW)
            if self.test_proxy(proxy):
                self.log(f"[+] Proxy working: {proxy}", Fore.GREEN)
                return proxy
                
            self.log(f"[!] Proxy not working: {proxy}", Fore.RED)
            
        self.log("[!] No working proxies found. Continuing without proxy.", Fore.RED)
        return None

    def initialize_driver(self, thread_id=0): 
        """Set up Chrome options for WebDriver with optional proxy"""
        self.log(f"[~] Thread {thread_id}: Loading driver, please wait...", Fore.YELLOW)
        options = Options()
        options.add_argument("--log-level=3")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")
        options.add_argument("--mute-audio")
        
        # Add ad-blocking capabilities
        options.add_argument("--disable-advertisements")
        options.add_argument("--disable-images")
        options.add_argument("--disable-extensions")
        
        # Add headless mode for improved stability
        # options.add_argument("--headless")
        
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2  # Block images to reduce page load time
        })
        
        # Add proxy if available and needed
        proxy = self.get_working_proxy() if self.proxies else None
        if proxy:
            self.log(f"[+] Thread {thread_id}: Using proxy: {proxy}", Fore.GREEN)
            proxy_settings = self.format_proxy_for_selenium(proxy)
            options.add_argument(f"--proxy-server={proxy_settings['httpProxy']}")
            
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_window_size(1280, 720)  # Set a specific window size
            driver.set_page_load_timeout(30)  # Set page load timeout
            driver.get("https://www.google.com")  # Test page load
            self.log(f"[+] Thread {thread_id}: Driver loaded successfully", Fore.GREEN)
            return driver
        except Exception as e:
            self.log(f"[!] Thread {thread_id}: WebDriver error: {str(e)}", Fore.RED)
            return None

    def setup_service_xpaths(self): # Define the base URL and xpaths for different services to interact with
        self.url = "https://zefoy.com"
        self.services = {
            "followers": ("/html/body/div[6]/div/div[2]/div/div/div[2]/div/button", 7),
            "hearts": ("/html/body/div[6]/div/div[2]/div/div/div[3]/div/button", 8),
            "comment_hearts": ("/html/body/div[6]/div/div[2]/div/div/div[4]/div/button", 9),
            "views": ("/html/body/div[6]/div/div[2]/div/div/div[5]/div/button", 10),
            "shares": ("/html/body/div[6]/div/div[2]/div/div/div[6]/div/button", 11),
            "favorites": ("/html/body/div[6]/div/div[2]/div/div/div[7]/div/button", 12),
        }

    def check_services(self, driver): # Check each service's availability
        service_status = {}
        for service, (xpath, div_index) in self.services.items():
            try:
                element = driver.find_element(By.XPATH, xpath)
                if element.is_enabled():
                    service_status[service] = (xpath, div_index, True, Fore.GREEN + "[WORKING]")
                else:
                    service_status[service] = (xpath, div_index, False, Fore.RED + "[OFFLINE]")
            except NoSuchElementException:
                service_status[service] = (xpath, div_index, False, Fore.RED + "[OFFLINE]")
        
        # Mark 'comment_hearts' service explicitly as not implemented
        if "comment_hearts" in service_status:
            xpath, div_index, _, _ = service_status["comment_hearts"]
            service_status["comment_hearts"] = (xpath, div_index, False, Fore.YELLOW + "[NOT IMPLEMENTED]")
        
        return service_status

    def start(self):
        """Main method to start the bot with multiple threads"""
        # Initialize first driver for setup
        self.main_driver = self.initialize_driver()
        if not self.main_driver:
            self.log("[!] Failed to initialize main driver. Exiting.", Fore.RED)
            return
            
        self.main_driver.get(self.url)
        self.log("Please complete the captcha on the website and press Enter here when done...", Fore.YELLOW)
        input()
        
        # Check services
        services_status = self.check_services(self.main_driver)
        
        # Display services
        for index, (service, details) in enumerate(services_status.items(), start=1):
            _, div_index, is_working, status = details
            self.log(f"[{index}] {service.ljust(20)} {status}", Fore.BLUE)
        
        # Select service
        choice = int(input(Fore.YELLOW + "[-] Choose an option: "))
        self.service_name = list(services_status.keys())[choice - 1]
        
        # Get service details
        self.service_xpath, self.div_index, _, _ = services_status[self.service_name]
        
        # Get video URLs
        urls_input = input(Fore.MAGENTA + "[-] Enter video URLs separated by a space: ")
        self.video_urls = urls_input.split()
        
        # Choose number of threads
        max_threads = min(len(self.video_urls), 5)  # Cap at 5 threads
        thread_count = 1
        if max_threads > 1:
            thread_input = input(Fore.YELLOW + f"[-] Enter number of threads (1-{max_threads}): ")
            try:
                thread_count = int(thread_input)
                thread_count = max(1, min(thread_count, max_threads))
            except ValueError:
                thread_count = 1
                
        self.max_threads = thread_count
        self.log(f"[+] Using {self.max_threads} thread(s)", Fore.GREEN)
        
        # Close main driver as we'll create new ones per thread
        self.main_driver.quit()
        
        # Put URLs in queue
        for url in self.video_urls:
            self.url_queue.put(url)
            
        # Start worker threads
        workers = []
        for i in range(self.max_threads):
            worker = threading.Thread(target=self.worker_thread, args=(i+1,))
            workers.append(worker)
            worker.start()
            
        # Start monitor thread for results
        monitor = threading.Thread(target=self.monitor_thread)
        monitor.start()
        
        try:
            # Wait for all workers to finish
            for worker in workers:
                worker.join()
                
            # Signal monitor to stop and wait for it
            self.stop_event.set()
            monitor.join()
            
            self.log("[+] All tasks completed", Fore.GREEN)
                
        except KeyboardInterrupt:
            self.log("\n[!] Script terminating...", Fore.RED)
            self.stop_event.set()
            
            # Wait for threads to finish gracefully
            for worker in workers:
                worker.join(timeout=1.0)
                
            monitor.join(timeout=1.0)
            
    def worker_thread(self, thread_id):
        """Worker thread to process URLs"""
        driver = self.initialize_driver(thread_id)
        if not driver:
            self.log(f"[!] Thread {thread_id}: Failed to initialize driver", Fore.RED)
            return
            
        try:
            # Navigate to the service page
            driver.get(self.url)
            self.log(f"[~] Thread {thread_id}: Please complete the captcha and press Enter...", Fore.YELLOW)
            input()  # Wait for captcha completion
            
            # Click on the service button
            driver.find_element(By.XPATH, self.service_xpath).click()
            
            consecutive_failures = 0
            
            while not self.url_queue.empty() and not self.stop_event.is_set():
                try:
                    # Get URL with timeout
                    try:
                        url = self.url_queue.get(timeout=1.0)
                    except queue.Empty:
                        break
                        
                    self.log(f"[+] Thread {thread_id}: Processing URL: {url}", Fore.CYAN)
                    success = self.perform_service_action(driver, url, thread_id)
                    
                    if success:
                        consecutive_failures = 0
                        self.result_queue.put((url, True, "Success"))
                    else:
                        consecutive_failures += 1
                        self.result_queue.put((url, False, "Failed to complete action"))
                        
                    # Add URL back to queue for continuous processing
                    if not self.stop_event.is_set():
                        self.url_queue.put(url)
                        
                    # If too many failures, try rotating proxy
                    if consecutive_failures >= 3:
                        self.log(f"[~] Thread {thread_id}: Too many failures, restarting driver", Fore.YELLOW)
                        driver.quit()
                        driver = self.initialize_driver(thread_id)
                        if not driver:
                            return
                            
                        # Navigate to the service page again
                        driver.get(self.url)
                        self.log(f"[~] Thread {thread_id}: Please complete the captcha and press Enter...", Fore.YELLOW)
                        input()  # Wait for captcha completion
                        
                        # Click on the service button
                        driver.find_element(By.XPATH, self.service_xpath).click()
                        consecutive_failures = 0
                    
                except Exception as e:
                    self.log(f"[!] Thread {thread_id}: Error: {str(e)}", Fore.RED)
                    self.result_queue.put((url if 'url' in locals() else "unknown", False, str(e)))
                    
        finally:
            if driver:
                driver.quit()
                
    def monitor_thread(self):
        """Monitor thread to track progress and display statistics"""
        success_count = 0
        failure_count = 0
        processed_urls = set()
        
        while not self.stop_event.is_set():
            try:
                # Get result with timeout
                try:
                    url, success, message = self.result_queue.get(timeout=1.0)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                        
                    processed_urls.add(url)
                    
                    # Log statistics periodically
                    if (success_count + failure_count) % 5 == 0:
                        total = success_count + failure_count
                        success_rate = (success_count / total) * 100 if total > 0 else 0
                        self.log(f"[STATS] URLs processed: {len(processed_urls)}, Success rate: {success_rate:.1f}%", Fore.MAGENTA)
                        
                except queue.Empty:
                    pass
                    
            except Exception as e:
                self.log(f"[!] Monitor error: {str(e)}", Fore.RED)
                
            # Sleep briefly to reduce CPU usage
            time.sleep(0.1)
            
    def perform_service_action(self, driver, video_url, thread_id): 
        """Perform the action for the chosen service on the provided video URL"""
        self.log(f"[+] Thread {thread_id}: Processing \"{video_url}\"", Fore.CYAN)
        
        # Execute JavaScript to remove ads
        try:
            driver.execute_script("""
                // Remove all iframes (ads)
                const iframes = document.querySelectorAll('iframe');
                for(let i=0; i<iframes.length; i++) {
                    iframes[i].remove();
                }
                
                // Remove all ad divs
                const adDivs = document.querySelectorAll('[id*="google_ads"],[id*="aswift"],[class*="adsbygoogle"]');
                for(let i=0; i<adDivs.length; i++) {
                    adDivs[i].remove();
                }
            """)
            self.log(f"[+] Thread {thread_id}: Removed ads via JavaScript", Fore.GREEN)
        except Exception as e:
            self.log(f"[!] Thread {thread_id}: Failed to remove ads: {str(e)}", Fore.RED)
        
        actions = [
            ("clear the URL input", f"/html/body/div[{self.div_index}]/div/form/div/input", "clear"),
            ("enter the video URL", f"/html/body/div[{self.div_index}]/div/form/div/input", "send_keys"),
            ("click the search button", f"/html/body/div[{self.div_index}]/div/form/div/div/button", "click"),
            ("click the send button", f"/html/body/div[{self.div_index}]/div/div/div[1]/div/form/button", "click"),
        ]

        for action_desc, xpath, action_type in actions:
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # First ensure no ads are blocking our elements
                    driver.execute_script("""
                        // Remove all iframes (ads) again
                        const iframes = document.querySelectorAll('iframe');
                        for(let i=0; i<iframes.length; i++) {
                            iframes[i].remove();
                        }
                    """)
                    
                    # Use a more reliable wait condition
                    wait = WebDriverWait(driver, 15, poll_frequency=0.5)
                    
                    # Try to locate the element
                    element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    
                    # Scroll into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)  # Small delay after scrolling
                    
                    # Wait for element to be clickable
                    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    
                    # Try different interaction methods
                    if action_type == "clear":
                        driver.execute_script("arguments[0].value = '';", element)
                    elif action_type == "send_keys":
                        driver.execute_script(f"arguments[0].value = '{video_url}';", element)
                    
                    # Try JavaScript click instead of Selenium click
                    if action_type == "click" or action_type not in ["clear", "send_keys"]:
                        try:
                            # First try normal click
                            element.click()
                        except (ElementClickInterceptedException, StaleElementReferenceException):
                            # If normal click fails, try JavaScript click
                            driver.execute_script("arguments[0].click();", element)
                    
                    self.log(f"[+] Thread {thread_id}: Successfully {action_desc}", Fore.GREEN)
                    
                    if action_desc == "click the search button":
                        time.sleep(5)  # Increase delay after clicking the search button
                    
                    # If we reach here, the action succeeded
                    break
                    
                except (TimeoutException, ElementClickInterceptedException, StaleElementReferenceException) as e:
                    self.log(f"[!] Thread {thread_id}: Attempt {retry+1}/{max_retries} - Could not {action_desc}: {str(e)}", Fore.RED)
                    
                    if retry == max_retries - 1:  # If this was the last retry
                        # Check for captcha reappearance
                        try:
                            captcha_element = driver.find_element(By.XPATH, "//form[contains(@action, 'captcha')]")
                            self.log(f"[!] Thread {thread_id}: Captcha detected. Please solve it and press Enter...", Fore.YELLOW)
                            input()
                            # Retry from beginning
                            return self.perform_service_action(driver, video_url, thread_id)
                        except NoSuchElementException:
                            # No captcha, it's another issue
                            if action_desc == "clear the URL input":
                                # If we can't even clear the input field, it's a serious problem
                                return False
                    else:
                        # Not the last retry yet - wait before retrying
                        time.sleep(3)

        # Custom wait time for each service after actions
        min_wait, max_wait = self.service_wait_times[self.service_name]
        wait_time = random.randint(min_wait, max_wait)
        self.countdown_timer(wait_time, thread_id)
        return True

    def countdown_timer(self, duration, thread_id=0):
        """Display a countdown timer for the specified duration"""
        for i in range(duration, 0, -1):
            if self.stop_event.is_set():
                break
                
            if i % 5 == 0 or i <= 5:  # Only print every 5 seconds or final 5 seconds
                self.log(f"Thread {thread_id}: Waiting for {i} seconds to proceed...", Fore.CYAN)
            time.sleep(1)

if __name__ == "__main__":
    bot = Bot()
    bot.start()
