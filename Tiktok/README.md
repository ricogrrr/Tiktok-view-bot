# TikTok Engagement Bot

A bot that uses Zefoy.com to boost TikTok engagement metrics (followers, hearts, views, shares, etc.).

## Installation

1. Make sure you have Python 3.8+ installed.
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Make sure you have Chrome browser installed.

## Usage

1. Run the bot:
   ```
   python main.py
   ```
2. Follow the on-screen instructions:
   - You can choose to use proxies or not
   - Complete the captcha when prompted
   - Select the service you want to use (hearts, views, shares, etc.)
   - Enter TikTok video URLs to boost

## Troubleshooting

### Common Issues:

1. **Ad-blocking Issues**: The bot now attempts to remove ads via JavaScript, but if you still encounter issues, consider running an ad-blocker in your browser.

2. **Captcha Problems**: Zefoy.com uses captchas to prevent automation. You need to solve these manually.

3. **Service Unavailability**: Zefoy.com services may be offline at times. Try a different service if one isn't working.

4. **Click Interception**: If elements are not being clicked properly, the bot will attempt multiple strategies to interact with them.

5. **Browser Disconnections**: If browser sessions keep disconnecting, try:
   - Ensuring you have a stable internet connection
   - Using proxies if available
   - Reducing the number of threads

## Disclaimer

This tool is for educational purposes only. Use at your own risk. Automating actions on TikTok may violate their Terms of Service. 