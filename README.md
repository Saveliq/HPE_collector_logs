Server Log Collector (collect5.py)
This Python script collects server information, IML logs, and AHS files from servers using the Redfish API. It processes multiple servers concurrently, saves data to JSON and AHS files, and logs errors for debugging. The script is designed for system administrators managing server infrastructure.
Prerequisites
Before running the script, ensure the following requirements are met:
System Requirements

Operating System: Windows, Linux, or macOS
Python Version: Python 3.6 or higher
Permissions: Write access to the directory where server_logs will be created
Network Access: Access to servers via HTTPS (port 443) using Redfish API

Python Dependencies
The script requires the following Python packages:

redfish: For interacting with the Redfish API
urllib3: For HTTP requests
Other standard libraries (json, csv, os, re, traceback, datetime, concurrent.futures) are included in Python

Install the required package using pip:
pip install redfish

Input File

File: servers.csv
Location: Same directory as collect5.py
Format: CSV file with UTF-8 encoding and the following columns:
ip: IP address of the server (e.g., 192.168.1.100)
username: Redfish API username
password: Redfish API password


Example servers.csv:ip,username,password
192.168.1.100,admin,password123
192.168.1.101,admin,password456


Notes:
Ensure the CSV file has a header row with ip, username, and password.
Rows missing any of these fields will be skipped with a warning.
Use UTF-8 encoding to avoid decoding errors.



Installation

Install Python:

Download and install Python 3.6+ from python.org.
Verify installation:python --version




Install Dependencies:

Install the redfish package:pip install redfish




Prepare the Script:

Save collect5.py to a working directory (e.g., /path/to/script/).
Place servers.csv in the same directory.


Verify Permissions:

Ensure you have write permissions in the directory to create the server_logs folder.
On Linux/macOS, you may need to run:chmod +w /path/to/script/





Usage

Prepare servers.csv:

Create or edit servers.csv with the IP addresses, usernames, and passwords of the servers.
Example:ip,username,password
192.168.1.100,admin,password123




Run the Script:

Open a terminal or command prompt.
Navigate to the script directory:cd /path/to/script/


Execute the script:python collect5.py




Configure Concurrent Processing:

When prompted, enter the number of simultaneous server processes (threads):Введите количество одновременных обработок (по умолчанию 10):


Enter a positive integer or press Enter to use the default (10).
Notes:
The number is capped at the number of servers in servers.csv to avoid unnecessary threads.
A higher number increases parallelism but may strain system resources or network.




Monitor Output:

The script will display progress for each server:Обработка сервера 192.168.1.100 начата
Сбор данных начат
Сбор данных завершен
Обработка сервера 192.168.1.100 завершена, данные сохранены в server_logs/CZJ442026K_20250427_164404
Обработано 1 из 2 серверов успешно


Errors are reported for failed servers:Ошибка при обработке сервера 192.168.1.101: ConnectionError: Connection timed out




Review Results:

Output Directory: server_logs (created in the script directory)
Folder Structure:
Successful servers: server_logs/{serial_number_or_ip}_{timestamp}/
Failed servers: server_logs/error_{ip}_{timestamp}/


Files per Server:
server_info.json: Raw Redfish data
parsed_data.json: Processed Redfish data
IML_logs.json: Up to 20 IML logs
{serial_number_or_ip}.ahs: AHS file (if available)
errors.log: Log of errors and informational messages


Fallback Logs: If the log directory is unavailable, logs are saved to server_logs/fallback_errors_{ip}.log.


Check Summary:

The script ends with a summary:Обработка завершена: 1/2 серверов успешно обработано
Сбой при обработке серверов: 192.168.1.101





Troubleshooting
Common Issues

"No such file or directory: servers.csv":

Ensure servers.csv is in the same directory as collect5.py.
Verify the file name is exactly servers.csv (case-sensitive on Linux).


"UnicodeDecodeError" in CSV Reading:

The CSV file must be UTF-8 encoded. If it’s in another encoding (e.g., Windows-1251):
Convert it to UTF-8 using a text editor (e.g., Notepad++ or VS Code).
Example in VS Code:
Open servers.csv.
Select "Save with Encoding" and choose UTF-8.






Connection Errors:

Symptoms: Errors like ConnectionError: Connection timed out or InvalidCredentialsError.
Solutions:
Verify the server IP, username, and password in servers.csv.
Ensure the server is reachable (e.g., ping 192.168.1.100).
Check if the server supports Redfish API and HTTPS (port 443).




Permission Denied:

Symptoms: Errors like [Errno 13] Permission denied when creating server_logs.
Solutions:
Run the script with elevated permissions:sudo python collect5.py


Change directory permissions:chmod -R u+w /path/to/script/






AHS File Not Created:

The AHS file ({serial_number_or_ip}.ahs) is only created if the server responds to the AHS request.
Check errors.log for details (e.g., HTTP 404 or ConnectionError).
Verify the server supports AHS downloads via Redfish.



Debugging

Check Logs:
Open server_logs/{folder}/errors.log for detailed error messages and stack traces.
Example log entry:2025-04-27 16:44:04.123456 - ERROR - Сервер 192.168.1.100 - Ошибка авторизации: InvalidCredentialsError: Invalid credentials




Enable Verbose Output:
Modify _log_error and _log_info to print to console for real-time debugging:def _log_error(self, message):
    msg = f"{datetime.now()} - ERROR - Сервер {self.server_ip} - {message}"
    print(msg)
    ...





Output Details

Successful Servers:
Folder: server_logs/{serial_number_or_ip}_{YYYYMMDD_HHMMSS}/
Files:
server_info.json: Full Redfish resource data
parsed_data.json: Processed Redfish data
IML_logs.json: Up to 20 IML logs
{serial_number_or_ip}.ahs: AHS file
errors.log: Log of operations and errors




Failed Servers:
Folder: server_logs/error_{ip}_{YYYYMMDD_HHMMSS}/
Files: Partial data (e.g., server_info.json, errors.log) if collected before the error


Fallback Logs:
File: server_logs/fallback_errors_{ip}.log
Used if the primary log directory is unavailable



Notes

Concurrency: The script uses multiple threads (max_workers) to process servers concurrently. Be cautious with high values on resource-constrained systems.
Security: Store servers.csv securely, as it contains sensitive credentials.
Redfish Compatibility: The script assumes servers support Redfish API v1. Ensure compatibility with your hardware.
IML Logs: Only the last 20 IML logs are collected, as defined by MAX_IML_LOGS.

Example Workflow

Create servers.csv:ip,username,password
192.168.1.100,admin,password123
192.168.1.101,admin,password456


Run the script:python collect5.py


Enter 5 when prompted for concurrent processes.
Check server_logs for output:
server_logs/CZJ442026K_20250427_164404/ (successful)
server_logs/error_192.168.1.101_20250427_164405/ (failed)



License
This script is provided as-is without warranty. Use at your own risk.
