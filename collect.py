# Импортируем необходимые библиотеки
import redfish  # Для работы с Redfish API
import json  # Для работы с JSON-данными
import urllib3  # Для выполнения HTTP-запросов
import csv  # Для чтения CSV-файлов
import os  # Для работы с файловой системой
import re  # Для работы с регулярными выражениями
import traceback  # Для получения стека вызовов при ошибках
from datetime import datetime  # Для работы с датой и временем
from concurrent.futures import ThreadPoolExecutor, as_completed  # Для многопоточной обработки

# Отключаем предупреждения о небезопасных HTTPS-соединениях
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Класс для взаимодействия с Redfish API
class RedfishClient:
    def __init__(self, base_url, username, password, log_file, server_ip):
        # Путь к файлу логов
        self.log_file = log_file
        # IP-адрес сервера для идентификации в логах
        self.server_ip = server_ip
        # Проверяем, что base_url начинается с https://
        if not base_url.startswith("https://"):
            self._log_error("Неверный формат base_url: должен начинаться с https://")
            self.client = None
            return
        # Проверяем, что имя пользователя и пароль не пустые
        if not username or not password:
            self._log_error("Пустое имя пользователя или пароль")
            self.client = None
            return
        try:
            # Логируем попытку создания клиента
            self._log_info(f"Создание клиента Redfish для {base_url}")
            # Создаем клиент Redfish
            self.client = redfish.redfish_client(
                base_url=base_url,
                username=username,
                password=password,
                default_prefix="/redfish/v1"
            )
            self._log_info("Клиент успешно создан")
        except redfish.rest.v1.InvalidCredentialsError as e:
            # Обрабатываем ошибку неверных учетных данных
            self._log_error(f"Ошибка авторизации: неверные учетные данные: {str(e)}")
            self.client = None
        except ValueError as e:
            # Обрабатываем ошибки валидации параметров
            self._log_error(f"Ошибка валидации параметров: {str(e)}")
            self.client = None
        except Exception as e:
            # Обрабатываем непредвиденные ошибки с полным стеком вызовов
            self._log_error(f"Неизвестная ошибка при создании клиента: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
            self.client = None

    def login(self):
        # Проверяем, инициализирован ли клиент
        if self.client is None:
            self._log_error("Клиент не инициализирован")
            return False
        try:
            # Логируем попытку авторизации
            self._log_info("Попытка авторизации")
            self.client.login()
            self._log_info("Авторизация успешно выполнена")
            return True
        except redfish.rest.v1.InvalidCredentialsError as e:
            # Обрабатываем ошибку неверных учетных данных
            self._log_error(f"Ошибка авторизации: неверные учетные данные: {str(e)}")
            return False
        except Exception as e:
            # Обрабатываем другие ошибки авторизации
            self._log_error(f"Ошибка авторизации: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
            return False

    def logout(self):
        # Проверяем, существует ли клиент
        if self.client is not None:
            try:
                # Логируем начало выхода
                self._log_info("Выход из клиента")
                self.client.logout()
                self._log_info("Выход из клиента выполнен")
            except Exception as e:
                # Логируем ошибки при выходе
                self._log_error(f"Ошибка при выходе: {type(e).__name__}: {str(e)}")

    def get(self, uri):
        # Проверяем, инициализирован ли клиент
        if self.client is None:
            self._log_error("Клиент не инициализирован")
            return None
        try:
            # Логируем начало GET-запроса
            self._log_info(f"Выполняется GET-запрос к {uri}")
            response = self.client.get(uri)
            if response.status == 200:
                # Логируем успешный запрос
                self._log_info(f"Успешный запрос к {uri}")
                return response
            else:
                # Логируем ошибку HTTP-статуса
                self._log_error(f"Ошибка при получении {uri}: HTTP {response.status}")
                return None
        except Exception as e:
            # Логируем исключения при запросе
            self._log_error(f"Исключение при запросе {uri}: {type(e).__name__}: {str(e)}")
            return None

    def _log_error(self, message):
        # Определяем путь к файлу логов
        log_path = self.log_file
        # Если директория лога не существует, используем резервный лог
        if not os.path.exists(os.path.dirname(log_path)):
            log_path = os.path.join("server_logs", f"fallback_errors_{self.server_ip}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        # Записываем сообщение об ошибке в лог
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} - ERROR - Сервер {self.server_ip} - {message}\n")

    def _log_info(self, message):
        # Определяем путь к файлу логов
        log_path = self.log_file
        # Если директория лога не существует, используем резервный лог
        if not os.path.exists(os.path.dirname(log_path)):
            log_path = os.path.join("server_logs", f"fallback_errors_{self.server_ip}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        # Записываем информационное сообщение в лог
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} - INFO - Сервер {self.server_ip} - {message}\n")

# Класс для сбора информации с серверов через Redfish
class ServerInfoCollector:
    def __init__(self, client):
        # Сохраняем клиент Redfish
        self.client = client
        # Словарь для хранения собранных данных
        self.collected_data = {}
        # Регулярные выражения для включения ссылок
        self.INCLUDE_PATTERNS = [
            r"/redfish/v1/Systems(/.*)?",
            r"/redfish/v1/Managers(/.*)?",
            r"/redfish/v1/Chassis(/.*)?",
            r"/redfish/v1/LogServices(/.*)?",
        ]
        # Регулярные выражения для исключения ссылок
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
            r".*SL/Entries.*",
            r".*Event/Entries.*",
        ]
        # URL для коллекции IML-логов
        self.IML_ENTRIES_URL = self.normalize_url("/redfish/v1/Systems/1/LogServices/IML/Entries/")
        # Максимальное количество IML-логов для сбора
        self.MAX_IML_LOGS = 20

    @staticmethod
    def normalize_url(url):
        # Удаляет завершающий слеш из URL
        return url.rstrip('/')

    @staticmethod
    def extract_links(data):
        # Извлекает все ссылки (@odata.id) из данных
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
        # Проверяет, соответствует ли ссылка паттернам включения и не попадает под исключения
        normalized_link = self.normalize_url(link)
        for pattern in self.EXCLUDE_PATTERNS:
            if re.match(pattern, normalized_link):
                return False
        for pattern in self.INCLUDE_PATTERNS:
            if re.match(pattern, normalized_link):
                return True
        return False

    def collect_resources(self, output_file=None):
        # Собирает ресурсы с сервера через Redfish API
        root_url = self.normalize_url("/redfish/v1")
        to_process = [root_url]
        visited = set()
        file_handle = open(output_file, "w", encoding="utf-8") if output_file else None
        try:
            self.client._log_info("Начало сбора ресурсов")
            print("Сбор данных начат")
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
                    if normalized_url == self.IML_ENTRIES_URL:
                        # Обрабатываем IML-логи, беря последние MAX_IML_LOGS записей
                        members = data.get("Members", [])[-self.MAX_IML_LOGS:]
                        for entry in members:
                            entry_url = self.normalize_url(entry.get("@odata.id", ""))
                            if entry_url and entry_url not in visited and entry_url not in to_process:
                                to_process.append(entry_url)
                    else:
                        # Извлекаем и добавляем новые ссылки для обработки
                        links = self.extract_links(data)
                        for link in links:
                            normalized_link = self.normalize_url(link)
                            if normalized_link not in visited and normalized_link not in to_process and self.is_valid_link(normalized_link):
                                to_process.append(normalized_link)
            self.client._log_info("Сбор ресурсов завершен")
            print("Сбор данных завершен")
        except Exception as e:
            # Логируем ошибки при сборе ресурсов
            self.client._log_error(f"Ошибка при сборе ресурсов: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
            print(f"Ошибка при сборе данных: {e}")
        finally:
            if file_handle:
                # Сохраняем собранные данные в файл
                json.dump(self.collected_data, file_handle, indent=2, ensure_ascii=False)
                file_handle.close()

    def collect_iml_logs(self):
        # Собирает IML-логи из собранных данных
        try:
            entries_url = self.IML_ENTRIES_URL
            entries_data = self.collected_data.get(entries_url, {})
            iml_logs = [
                self.collected_data.get(self.normalize_url(entry["@odata.id"]), {})
                for entry in entries_data.get("Members", [])
            ]
            self.client._log_info(f"Собрано {len(iml_logs)} IML-логов")
            return iml_logs
        except Exception as e:
            # Логируем ошибки при сборе IML-логов
            self.client._log_error(f"Ошибка при сборе IML-логов: {type(e).__name__}: {str(e)}")
            print(f"Ошибка при сборе IML-логов: {e}")
            return []

# Читает список серверов из CSV-файла
def read_servers_from_csv(csv_file):
    servers = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Проверяем наличие обязательных полей
                if 'ip' in row and 'username' in row and 'password' in row:
                    servers.append({
                        'ip': row['ip'],
                        'username': row['username'],
                        'password': row['password']
                    })
                else:
                    print("Пропущена строка в CSV: отсутствуют необходимые поля")
        return servers
    except Exception as e:
        # Логируем ошибки чтения CSV
        print(f"Ошибка чтения CSV файла: {e}")
        return []

# Обрабатывает данные одного сервера
def process_server(server, output_dir):
    ip = server['ip']
    print(f"Обработка сервера {ip} начата")
    # Формируем временную папку с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(output_dir, f"temp_{ip}_{timestamp}")
    os.makedirs(temp_dir, exist_ok=True)
    log_file = os.path.join(temp_dir, "errors.log")
    # Создаем клиент Redfish
    client = RedfishClient(f"https://{ip}", server['username'], server['password'], log_file, ip)
    # Проверяем инициализацию и авторизацию
    if client.client is None or not client.login():
        print(f"Пропуск сервера {ip} из-за ошибки инициализации или авторизации")
        error_dir = os.path.join(output_dir, f"error_{ip}_{timestamp}")
        os.rename(temp_dir, error_dir)
        print(f"Логи ошибок сохранены в {error_dir}")
        return False
    try:
        # Собираем данные с сервера
        collector = ServerInfoCollector(client)
        server_info_file = os.path.join(temp_dir, "server_info.json")
        collector.collect_resources(output_file=server_info_file)

        # Извлекаем серийный номер
        serial_number = None
        system_data = collector.collected_data.get("/redfish/v1/Systems/1", {})
        if "SerialNumber" in system_data:
            serial_number = system_data["SerialNumber"].strip()

        # Используем серийный номер или IP для имени папки
        folder_name = serial_number if serial_number else ip
        final_dir = os.path.join(output_dir, f"{folder_name}_{timestamp}")

        # Собираем IML-логи
        iml_logs = collector.collect_iml_logs()

        # Сохраняем собранные данные в JSON-файлы
        with open(os.path.join(temp_dir, "IML_logs.json"), "w", encoding="utf-8") as f:
            json.dump(iml_logs, f, indent=2, ensure_ascii=False)

        # Запрашиваем и сохраняем AHS-файл
        ahs_links_args = ["minimalDL=1&&days=1", "days=1", "days=7", "downloadAll=1"]
        ahs_filename = f"{folder_name}.ahs"
        ahs_file = os.path.join(temp_dir, ahs_filename)
        ahs_response = None
        for ahs_link in ahs_links_args:
            ahs_response = client.get(f"/ahsdata/{folder_name}.ahs?{ahs_link}")
            if ahs_response:
                with open(ahs_file, "wb") as f:
                    f.write(ahs_response.read)
                client._log_info(f"AHS-файл сохранен: {ahs_filename}")
                break

        # Переименовываем временную папку в окончательную
        os.rename(temp_dir, final_dir)
        client.log_file = os.path.join(final_dir, "errors.log")  # Обновляем путь к лог-файлу
        print(f"Обработка сервера {ip} завершена, данные сохранены в {final_dir}")
        return True
    except Exception as e:
        # Логируем и обрабатываем ошибки обработки сервера
        client._log_error(f"Ошибка обработки сервера: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
        print(f"Ошибка при обработке сервера {ip}: {e}")
        error_dir = os.path.join(output_dir, f"error_{ip}_{timestamp}")
        os.rename(temp_dir, error_dir)
        client.log_file = os.path.join(error_dir, "errors.log")  # Обновляем путь к лог-файлу
        print(f"Частично собранные данные сохранены в {error_dir}")
        return False
    finally:
        # Выполняем выход из клиента
        client.logout()

# Основная функция программы
def main():
    # Константы
    CSV_FILE = "servers.csv"  # Файл с данными серверов
    OUTPUT_DIR = "server_logs"  # Папка для сохранения логов
    DEFAULT_MAX_WORKERS = 10  # Количество потоков по умолчанию

    # Создаем выходную папку, если она не существует
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Запуск сбора логов серверов")

    # Читаем список серверов из CSV
    servers = read_servers_from_csv(CSV_FILE)
    if not servers:
        print("Серверы не найдены. Проверьте CSV файл.")
        return
    print(f"Всего серверов для обработки: {len(servers)}")

    # Запрашиваем количество одновременных обработок
    max_workers = DEFAULT_MAX_WORKERS
    try:
        user_input = input(f"Введите количество одновременных обработок (по умолчанию {DEFAULT_MAX_WORKERS}): ").strip()
        if user_input:
            max_workers = int(user_input)
            if max_workers < 1:
                print(f"Ошибка: число должно быть положительным. Используется значение по умолчанию: {DEFAULT_MAX_WORKERS}")
                max_workers = DEFAULT_MAX_WORKERS
            elif max_workers > len(servers):
                print(f"Предупреждение: введенное число ({max_workers}) больше количества серверов ({len(servers)}). Установлено значение: {len(servers)}")
                max_workers = len(servers)
    except ValueError:
        print(f"Ошибка: введено некорректное значение. Используется значение по умолчанию: {DEFAULT_MAX_WORKERS}")
        max_workers = DEFAULT_MAX_WORKERS

    print(f"Количество одновременных обработок: {max_workers}")

    # Обрабатываем серверы в многопоточном режиме
    success_count = 0
    failed_servers = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_server = {executor.submit(process_server, server, OUTPUT_DIR): server for server in servers}
        for future in as_completed(future_to_server):
            server = future_to_server[future]
            try:
                result = future.result()
                if result:
                    success_count += 1
                else:
                    failed_servers.append(server['ip'])
                print(f"Обработано {success_count} из {len(servers)} серверов успешно")
            except Exception as e:
                print(f"Ошибка при обработке сервера {server['ip']}: {type(e).__name__}: {str(e)}")
                failed_servers.append(server['ip'])

    # Выводим итоговую статистику
    print(f"Обработка завершена: {success_count}/{len(servers)} серверов успешно обработано")
    if failed_servers:
        print(f"Сбой при обработке серверов: {', '.join(failed_servers)}")

# Точка входа программы
if __name__ == "__main__":
    main()