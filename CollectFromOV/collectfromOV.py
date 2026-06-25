import json
import urllib3
import os
import re
import csv
import traceback
import redfish
from hpOneView.oneview_client import OneViewClient
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Отключаем предупреждения о небезопасных HTTPS-соединениях
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RedfishClient:
    def __init__(self, base_url, log_file, server_ip, session_key):
        self.log_file = log_file
        self.server_ip = server_ip
        # Сохраняем токен как строку для передачи в заголовках
        self.session_key = session_key
        
        if not base_url.startswith("https://"):
            self._log_error("Неверный формат base_url: должен начинаться с https://")
            self.client = None
            return

        if not session_key:
            self._log_error("Пустой SSO токен")
            self.client = None
            return

        try:
            self._log_info(f"Создание клиента Redfish для {base_url} (использование SSO)")
            # Инициализируем базовый HTTP-клиент
            self.client = redfish.redfish_client(
                base_url=base_url,
                default_prefix="/redfish/v1"
            )
            self._log_info("Клиент успешно создан")
        except Exception as e:
            self._log_error(f"Ошибка при создании клиента: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
            self.client = None

    def login(self):
        if self.client is None:
            self._log_error("Клиент не инициализирован")
            return False
        try:
            self._log_info("Проверка валидности SSO токена в iLO...")
            # ВАЖНО: Делаем запрос к ЗАЩИЩЕННОМУ эндпоинту и ЯВНО передаем заголовок X-Auth-Token
            headers = {'X-Auth-Token': self.session_key}
            response = self.client.get("/redfish/v1/Systems", headers=headers)
            
            if response and response.status == 200:
                self._log_info("SSO токен успешно валидирован iLO")
                return True
            else:
                status_code = response.status if response else "Нет ответа"
                self._log_error(f"iLO отклонил токен OneView. Код ответа: {status_code}")
                return False
        except Exception as e:
            self._log_error(f"Ошибка авторизации по токену: {type(e).__name__}: {str(e)}")
            return False

    def logout(self):
        # Для SSO-токенов от OneView классический logout не работает и не требуется.
        # Токен сам инвалидируется сервером OneView/iLO по истечению времени.
        self._log_info("Закрытие сессии скрипта (очистка данных клиента)")
        self.client = None

    def get(self, uri):
        if self.client is None:
            self._log_error("Клиент не инициализирован")
            return None
        try:
            self._log_info(f"Выполняется GET-запрос к {uri}")
            
            # ВАЖНО: Явно добавляем заголовок авторизации в КАЖДЫЙ GET-запрос
            headers = {'X-Auth-Token': self.session_key}
            response = self.client.get(uri, headers=headers)
            
            if response.status == 200:
                self._log_info(f"Успешный запрос к {uri}")
                return response
            else:
                self._log_error(f"Ошибка при получении {uri}: HTTP {response.status}")
                return None
        except Exception as e:
            self._log_error(f"Исключение при запросе {uri}: {type(e).__name__}: {str(e)}")
            return None

    def _log_error(self, message):
        log_path = self.log_file
        if not os.path.exists(os.path.dirname(log_path)):
            log_path = os.path.join("server_logs", f"fallback_errors_{self.server_ip}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} - ERROR - Сервер {self.server_ip} - {message}\n")

    def _log_info(self, message):
        log_path = self.log_file
        if not os.path.exists(os.path.dirname(log_path)):
            log_path = os.path.join("server_logs", f"fallback_errors_{self.server_ip}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} - INFO - Сервер {self.server_ip} - {message}\n")


class ServerInfoCollector:
    def __init__(self, client):
        self.client = client
        self.collected_data = {}
        self.INCLUDE_PATTERNS = [
            r"/redfish/v1/Systems(/.*)?",
            r"/redfish/v1/Managers(/.*)?",
            r"/redfish/v1/Chassis(/.*)?",
            r"/redfish/v1/LogServices(/.*)?",
        ]
        self.EXCLUDE_PATTERNS = [
            r"/redfish/v1/\$metadata",
            r"/redfish/v1/odata",
            r"/redfish/v1/Schemas(/.*)?",
            r"/redfish/v1/JsonSchemas(/.*)?",
            r"/redfish/v1/SessionService(/.*)?",
            r"/redfish/v1/TelemetryService(/.*)?",
            r"/redfish/v1/Registries(/.*)?",
            r"/redfish/v1/AccountService(/.*)?",
            r"/redfish/v1/EventService(/.*)?",
            r"/redfish/v1/Managers/.*DateTime.*",
            r"/redfish/v1/Managers/.*Federation.*",
            r"/redfish/v1/Managers/.*Service.*",
            r"/redfish/v1/Managers/.*VirtualMedia.*",
            r"/redfish/v1/Chassis/.*PowerMeter.*",
            r"/redfish/v1/Chassis/.*FederatedGroup.*",
            r"/redfish/v1/Chassis/.*Temperatures.*",
            r".*IEL.*",
            r".*IML.*",
            r".*SL/Entries.*",
            r".*Event/Entries.*",
        ]

    @staticmethod
    def normalize_url(url):
        return url.rstrip('/')

    @staticmethod
    def extract_links(data):
        result = []
        if isinstance(data, dict):
            if "@odata.id" in data:
                result.append(ServerInfoCollector.normalize_url(data["@odata.id"]))
            for value in data.values():
                result.extend(ServerInfoCollector.extract_links(value))
        elif isinstance(data, list):
            for item in data:
                result.extend(ServerInfoCollector.extract_links(item))
        return result

    def is_valid_link(self, link):
        normalized_link = self.normalize_url(link)
        for pattern in self.EXCLUDE_PATTERNS:
            if re.match(pattern, normalized_link):
                return False
        for pattern in self.INCLUDE_PATTERNS:
            if re.match(pattern, normalized_link):
                return True
        return False

    def collect_resources(self, output_file=None):
        root_url = self.normalize_url("/redfish/v1")
        to_process = [root_url]
        visited = set()
        file_handle = open(output_file, "w", encoding="utf-8") if output_file else None
        try:
            self.client._log_info("Начало сбора ресурсов")
            while to_process:
                current_url = to_process.pop(0)
                normalized_url = self.normalize_url(current_url)
                if normalized_url in visited:
                    continue
                visited.add(normalized_url)
                response = self.client.get(current_url)
                if response and response.status == 200:
                    data = response.dict
                    self.collected_data[normalized_url] = data
                    links = self.extract_links(data)
                    for link in links:
                        normalized_link = self.normalize_url(link)
                        if normalized_link not in visited and normalized_link not in to_process and self.is_valid_link(normalized_link):
                            to_process.append(normalized_link)
            self.client._log_info("Сбор ресурсов завершен")
        except Exception as e:
            self.client._log_error(f"Ошибка при сборе ресурсов: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
        finally:
            if file_handle:
                json.dump(self.collected_data, file_handle, indent=2, ensure_ascii=False)
                file_handle.close()


def read_ov_configs_from_csv(csv_file):
    """
    Читает ВСЕ конфигурации OneView из CSV файла и возвращает их списком.
    """
    configs = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'ip' in row and 'username' in row and 'password' in row:
                    configs.append({
                        "ip": row['ip'].strip(),
                        "credentials": {
                            "userName": row['username'].strip(),
                            "password": row['password'].strip()
                        }
                    })
        return configs
    except FileNotFoundError:
        print(f"Ошибка: Файл {csv_file} не найден.")
        return []
    except Exception as e:
        print(f"Ошибка чтения CSV файла конфигурации OneView: {e}")
        return []


def get_all_servers_from_ov(oneview_client, ov_ip):
    """
    Получает список всех серверов из OneView и формирует список для обработки.
    """
    servers_to_process = []
    print(f"  Получение списка серверов из OneView {ov_ip}...")
    try:
        server_hardware_list = oneview_client.server_hardware.get_all()
        print(f"  Найдено {len(server_hardware_list)} серверов в OneView {ov_ip}.")

        for server_hw in server_hardware_list:
            server_name = server_hw.get('name', 'Unknown')
            server_uri = server_hw.get('uri')
            
            if not server_uri:
                print(f"  Пропуск сервера {server_name}: отсутствует URI")
                continue

            if not server_hw.get('mpHostInfo'):
                print(f"  Пропуск сервера {server_name}: нет информации об управлении (iLO)")
                continue

            try:
                # Прямой REST запрос к OneView API
                remote_console_uri = f"{server_uri}/remoteConsoleUrl"
                response = oneview_client.connection.get(remote_console_uri)
                rc_url = response.get('remoteConsoleUrl', '')

                if not rc_url:
                    print(f"  Пропуск {server_name}: OneView вернул пустой URL удаленной консоли")
                    continue
                
                ip_match = re.search(r'addr=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', rc_url, re.I)
                token_match = re.search(r'sessionkey=([^&]+)', rc_url, re.I)
                
                if ip_match and token_match:
                    ilo_ip = ip_match.group(1)
                    sso_token = token_match.group(1)
                    servers_to_process.append({
                        'name': server_name,
                        'ip': ilo_ip,
                        'token': sso_token,
                        'source_ov': ov_ip
                    })
                else:
                    print(f"  Пропуск {server_name}: Не удалось извлечь IP или токен из URL")
            
            except Exception as e:
                print(f"  Ошибка получения SSO токена для {server_name}: {e}")
                
        return servers_to_process
    except Exception as e:
        print(f"  Ошибка связи с OneView {ov_ip} при получении списка серверов: {e}")
        return []


def process_server(server, output_dir):
    ip = server['ip']
    name = server['name']
    token = server['token']
    
    print(f"Обработка сервера {name} ({ip}) начата")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(output_dir, f"temp_{ip}_{timestamp}")
    os.makedirs(temp_dir, exist_ok=True)
    log_file = os.path.join(temp_dir, "errors.log")
    
    # Создаем клиент Redfish с SSO токеном
    client = RedfishClient(
        base_url=f"https://{ip}", 
        log_file=log_file, 
        server_ip=ip, 
        session_key=token
    )
    
    # Проверяем валидность токена
    if client.client is None or not client.login():
        print(f"Пропуск сервера {name} ({ip}) из-за ошибки валидации токена сессии")
        error_dir = os.path.join(output_dir, f"error_{ip}_{timestamp}")
        os.rename(temp_dir, error_dir)
        return False
        
    try:
        collector = ServerInfoCollector(client)
        server_info_file = os.path.join(temp_dir, "server_info.json")
        collector.collect_resources(output_file=server_info_file)

        serial_number = None
        system_data = collector.collected_data.get("/redfish/v1/Systems/1", {})
        if "SerialNumber" in system_data:
            serial_number = system_data["SerialNumber"].strip()

        folder_name = serial_number if serial_number else (name.replace(" ", "_") if name else ip)
        final_dir = os.path.join(output_dir, f"{folder_name}_{timestamp}")

        os.rename(temp_dir, final_dir)
        client.log_file = os.path.join(final_dir, "errors.log")
        print(f"Обработка сервера {name} ({ip}) успешно завершена, данные в {final_dir}")
        return True
    except Exception as e:
        client._log_error(f"Ошибка обработки сервера: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
        print(f"Ошибка при обработке сервера {name} ({ip}): {e}")
        error_dir = os.path.join(output_dir, f"error_{ip}_{timestamp}")
        os.rename(temp_dir, error_dir)
        client.log_file = os.path.join(error_dir, "errors.log")
        return False
    finally:
        client.logout()
        del client


def main():
    OV_CSV_FILE = "ov_config.csv"
    OUTPUT_DIR = "server_logs"
    DEFAULT_MAX_WORKERS = 10

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Запуск сбора логов серверов через интеграцию с OneView (последовательная обработка)")

    # 1. Читаем список OneView из CSV
    ov_configs = read_ov_configs_from_csv(OV_CSV_FILE)
    
    if not ov_configs:
        print(f"Критическая ошибка: Не найдено ни одной конфигурации OneView в {OV_CSV_FILE}.")
        return

    # Запрашиваем настройки потоков один раз в начале
    max_workers_input = DEFAULT_MAX_WORKERS
    try:
        user_input = input(f"Введите максимальное количество одновременных потоков на один OneView (по умолчанию {DEFAULT_MAX_WORKERS}): ").strip()
        if user_input:
            max_workers_input = int(user_input)
            if max_workers_input < 1:
                max_workers_input = DEFAULT_MAX_WORKERS
    except ValueError:
        max_workers_input = DEFAULT_MAX_WORKERS

    print(f"Максимальное количество потоков для каждого OneView установлено на: {max_workers_input}\n")

    # Глобальная статистика
    total_success_count = 0
    total_failed_servers = []
    total_servers_processed = 0

    # 2. Проходим циклом по КАЖДОМУ OneView и обрабатываем его сервера
    for index, config in enumerate(ov_configs, 1):
        ov_ip = config['ip']
        print(f"\n=======================================================")
        print(f"[{index}/{len(ov_configs)}] Подключение к OneView: {ov_ip}")
        print(f"=======================================================")
        
        try:
            oneview_client = OneViewClient(config)
            # Собираем серверы только из текущего OneView
            servers_from_ov = get_all_servers_from_ov(oneview_client, ov_ip)
            
            if not servers_from_ov:
                print(f"  В OneView {ov_ip} не найдено серверов для обработки.")
                continue
                
            print(f"  Успешно получены доступы к {len(servers_from_ov)} серверам из {ov_ip}.")
            total_servers_processed += len(servers_from_ov)
            
            # Ограничиваем количество потоков, если серверов меньше, чем max_workers
            current_max_workers = min(max_workers_input, len(servers_from_ov))
            print(f"  Запуск параллельного сбора ({current_max_workers} потоков) для OneView {ov_ip}...")
            
            ov_success = 0
            ov_failed = []
            
            # 3. Запускаем параллельную обработку серверов ТОЛЬКО текущего OneView
            with ThreadPoolExecutor(max_workers=current_max_workers) as executor:
                future_to_server = {executor.submit(process_server, server, OUTPUT_DIR): server for server in servers_from_ov}
                for future in as_completed(future_to_server):
                    server = future_to_server[future]
                    try:
                        result = future.result()
                        if result:
                            ov_success += 1
                            total_success_count += 1
                        else:
                            ov_failed.append(server['name'])
                            total_failed_servers.append(f"{server['name']} ({ov_ip})")
                    except Exception as e:
                        print(f"Ошибка в потоке для {server['name']}: {e}")
                        ov_failed.append(server['name'])
                        total_failed_servers.append(f"{server['name']} ({ov_ip})")

            # Выводим статистику по текущему OneView
            print(f"  Завершена обработка OneView {ov_ip}: {ov_success}/{len(servers_from_ov)} успешно.")
            if ov_failed:
                print(f"  Ошибки на серверах: {', '.join(ov_failed)}")

        except Exception as e:
            print(f"  Критическая ошибка при работе с OneView {ov_ip}: {e}")
            continue # Переходим к следующему OneView в списке

    # 4. Выводим итоговую глобальную статистику
    print(f"\n=======================================================")
    print(f"ВСЕ ЗАДАЧИ ЗАВЕРШЕНЫ. ИТОГОВАЯ СТАТИСТИКА:")
    print(f"Успешно обработано: {total_success_count} из {total_servers_processed} найденных серверов.")
    if total_failed_servers:
        print(f"Общий список проблемных серверов:\n - " + "\n - ".join(total_failed_servers))

if __name__ == "__main__":
    main()