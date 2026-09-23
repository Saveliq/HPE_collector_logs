# Импортируем необходимые библиотеки
import redfish  # Для работы с Redfish API
import json  # Для работы с JSON-данными
import urllib3  # Для выполнения HTTP-запросов
import csv  # Для чтения CSV-файлов
import os  # Для работы с файловой системой
import re  # Для работы с регулярными выражениями
import getpass  # Для скрытого ввода пароля
import traceback  # Для получения стека вызовов при ошибках
from datetime import datetime  # Для работы с датой и временем
from concurrent.futures import ThreadPoolExecutor, as_completed  # Для многопоточной обработки

# Отключаем предупреждения о небезопасных HTTPS-соединениях
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Класс для взаимодействия с Redfish API (прямая авторизация в iLO по логину/паролю)
class RedfishClient:
    # Таймаут одного HTTP-запроса (сек) и число повторов — чтобы недоступные
    # iLO не подвешивали поток на минуты, а быстро отбраковывались.
    CONNECT_TIMEOUT = 15
    MAX_RETRY = 2

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
            # Создаем клиент Redfish с таймаутом, чтобы не зависать на недоступных хостах
            self.client = redfish.redfish_client(
                base_url=base_url,
                username=username,
                password=password,
                default_prefix="/redfish/v1",
                timeout=self.CONNECT_TIMEOUT,
                max_retry=self.MAX_RETRY
            )
            self._log_info("Клиент успешно создан")
        except redfish.rest.v1.InvalidCredentialsError as e:
            # Обрабатываем ошибку неверных учетных данных
            self._log_error(f"Ошибка авторизации: неверные учетные данные: {str(e)}")
            self.client = None
        except redfish.rest.v1.RetriesExhaustedError:
            # Сервер недоступен (таймаут соединения) — пропускаем без длинного стека
            self._log_error(f"Сервер {server_ip} недоступен (таймаут соединения). Пропуск.")
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
            self.client.login(auth=redfish.rest.v1.AuthMethod.BASIC)
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
                try:
                    self.client.logout()  # закрыть Redfish-сессию
                except Exception as e:
                    self._log_error(f"Ошибка при logout: {type(e).__name__}: {str(e)}")

                try:
                    self.client.close()  # закрыть HTTP-сессию (ВАЖНО!)
                except Exception as e:
                    self._log_error(f"Ошибка при close: {type(e).__name__}: {str(e)}")

                self._log_info("Клиент полностью закрыт")
            except Exception as e:
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


# Класс для сбора ВСЕХ доступных ресурсов дерева Redfish
class ServerInfoCollector:
    """
    Обходит всё дерево Redfish, начиная с /redfish/v1, и собирает все ресурсы,
    на которые есть ссылки (@odata.id). Ограничений по разделам нет.
    """
    def __init__(self, client):
        # Сохраняем клиент Redfish
        self.client = client
        # Словарь для хранения собранных данных
        self.collected_data = {}
        # Регулярные выражения для включения ссылок — разрешаем все элементы Redfish
        

        self.INCLUDE_PATTERNS = [
            r"/redfish/v1/?$",                       # ServiceRoot: модель, версия, ServiceTag
            r"/redfish/v1/Systems(/.*)?",            # CPU, Memory, Storage, NIC, Boot, Health
            r"/redfish/v1/Chassis(/.*)?",            # Sensors, Power, Thermal, PCIe, адаптеры
            r"/redfish/v1/Managers(/.*)?",           # iDRAC: прошивка, сеть, FaultList
            r"/redfish/v1/UpdateService(/.*)?",      # FirmwareInventory — версии прошивок
            r"/redfish/v1/LicenseService(/.*)?",     # лицензии iDRAC
            r"/redfish/v1/JobService/Jobs(/.*)?",    # незавершённые/упавшие задания
        ]
        self.EXCLUDE_PATTERNS = [
            # --- протокол / схемы (чистый шум) ---
            r"/redfish/v1/\$metadata",
            r"/redfish/v1/odata",
            r"/redfish/v1/Schemas(/.*)?",
            r"/redfish/v1/JsonSchemas(/.*)?",
            r"/redfish/v1/Registries(/.*)?",
            # --- сервисы, не нужные для аппаратного аудита ---
            r"/redfish/v1/SessionService(/.*)?",
            r"/redfish/v1/AccountService(/.*)?",
            r"/redfish/v1/EventService(/.*)?",
            r"/redfish/v1/TelemetryService(/.*)?",   # только определения метрик, не значения
            r"/redfish/v1/TaskService(/.*)?",
            r"/redfish/v1/CertificateService(/.*)?",
            r"/redfish/v1/ComponentIntegrity(/.*)?",
            r"/redfish/v1/Fabrics(/.*)?",
            # --- базы ключей SecureBoot: ~585 сертификатов/подписей ---
            r"/redfish/v1/Systems/.*/SecureBoot(/.*)?",
            # --- лог-ЗАПИСИ: индекс LogServices и FaultList оставляем, массу SEL/LC режем ---
            r"/redfish/v1/Managers/.*/LogServices/Sel/Entries(/.*)?",
            r"/redfish/v1/Managers/.*/LogServices/Lclog/Entries(/.*)?",
            # --- Settings = желаемая конфигурация, а не текущее состояние ---
            r"/redfish/v1/.*/Settings$",
            # --- housekeeping iDRAC, не относится к железу ---
            r"/redfish/v1/Managers/.*/VirtualMedia(/.*)?",
            r"/redfish/v1/Managers/.*/Oem/Dell/Jobs(/.*)?",
            r"/redfish/v1/Managers/.*DellTimeService.*",
            r"/redfish/v1/Managers/.*RemoteSystemLogs.*",
            r"/redfish/v1/Managers/.*/Oem/Dell/Dell.*Service(/.*)?",
            r"/redfish/v1/Managers/.*vFlash.*",
            r"/redfish/v1/Managers/.*QuickSync.*",
            r"/redfish/v1/Managers/.*USBDevices.*",
            # --- сервисы деплоя/установки под Systems (действия, не состояние) ---
            r"/redfish/v1/Systems/.*/Oem/Dell/Dell.*Service(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellOSDeployment.*",
            # ===== доп. срез дублей и балласта (данные не теряются) =====
            # легаси-представление Power (#-фрагмент) — дубль /Sensors/*
            r"/redfish/v1/Chassis/.*/Power#/Voltages(/.*)?",
            r"/redfish/v1/Chassis/.*/Power#/PowerControl(/.*)?",
            # Dell Oem числовые сенсоры — дубль /Sensors/*, health берём из RollupStatus
            r"/redfish/v1/Systems/.*/Oem/Dell/DellNumericSensors(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellPSNumericSensors(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellSensors(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellPresenceAndStatusSensors(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellGPUSensors(/.*)?",
            # инвентарь слотов/видео/загрузки — не про состояние
            r"/redfish/v1/Systems/.*/Oem/Dell/DellSlots(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellVideo(/.*)?",
            r"/redfish/v1/Systems/.*/Oem/Dell/DellBootSources(/.*)?",
            r"/redfish/v1/Systems/.*/BootOptions(/.*)?",
            r"/redfish/v1/Systems/.*/SimpleStorage(/.*)?",       # легаси-дубль Storage
            r"/redfish/v1/Systems/.*/NetworkInterfaces(/.*)?",    # только ссылки, дубль
            r"/redfish/v1/Systems/.*/VirtualMedia(/.*)?",         # не про железо
            # PCIeFunctions — дубль PCIeDevices (сами устройства оставляем)
            r"/redfish/v1/.*/PCIeFunctions(/.*)?",
            # Assembly (part-numbers плат) — инвентарь, не health
            r"/redfish/v1/.*/Assembly#?(/.*)?$",
            # iDRAC config-блобы и обвязка (не состояние железа)
            r"/redfish/v1/Managers/.*/Oem/Dell/DellOpaqueManagementData(/.*)?",
            r"/redfish/v1/Managers/.*/ManagerDiagnosticData(/.*)?",
            r"/redfish/v1/Managers/.*/HostInterfaces(/.*)?",
            r"/redfish/v1/Managers/.*/SerialInterfaces(/.*)?",
            r"/redfish/v1/Managers/.*/PrivilegeRegistry(/.*)?",
            r"/redfish/v1/Managers/.*/NetworkProtocol/.+/Certificates(/.*)?",
        ]

    @staticmethod
    def normalize_url(url):
        # Удаляет завершающий слеш из URL
        if not isinstance(url, str):
            return None
        return url.rstrip('/')

    @staticmethod
    def extract_links(data):
        # Извлекает все ссылки (@odata.id) из данных
        result = []
        if isinstance(data, dict):
            odata_id = data.get("@odata.id")
            if isinstance(odata_id, str) and odata_id:
                result.append(ServerInfoCollector.normalize_url(odata_id))
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
        # Собирает все ресурсы дерева Redfish
        root_url = self.normalize_url("/redfish/v1")
        to_process = [root_url]
        visited = set()
        file_handle = open(output_file, "w", encoding="utf-8") if output_file else None
        try:
            self.client._log_info("Начало полного сбора ресурсов Redfish")
            print(f"Полный сбор ресурсов Redfish начат ({self.client.server_ip})")
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
                    # Извлекаем и добавляем новые ссылки для обработки
                    links = self.extract_links(data)
                    for link in links:
                        normalized_link = self.normalize_url(link)
                        if normalized_link not in visited and normalized_link not in to_process and self.is_valid_link(normalized_link):
                            to_process.append(normalized_link)
            self.client._log_info("Полный сбор ресурсов Redfish завершен")
            print(f"Полный сбор ресурсов Redfish завершен ({self.client.server_ip})")
        except Exception as e:
            # Логируем ошибки при сборе ресурсов
            self.client._log_error(f"Ошибка при сборе ресурсов: {type(e).__name__}: {str(e)}\nПолный стек: {traceback.format_exc()}")
            print(f"Ошибка при сборе данных: {e}")
        finally:
            if file_handle:
                # Сохраняем собранные данные в файл
                json.dump(self.collected_data, file_handle, indent=2, ensure_ascii=False)
                file_handle.close()


# Читает список серверов (iLO) из CSV-файла. В CSV только колонка 'ip'.
def read_servers_from_csv(csv_file):
    servers = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # В файле хранится только адрес; логин/пароль вводятся через консоль
                if 'ip' in row and row['ip'].strip():
                    servers.append({
                        'ip': row['ip'].strip(),
                        'username': None,  # будет заполнено из консоли
                        'password': None   # будет заполнено из консоли
                    })
                else:
                    print("Пропущена строка в CSV: отсутствует поле 'ip'")
        return servers
    except FileNotFoundError:
        print(f"Ошибка: Файл {csv_file} не найден.")
        return []
    except Exception as e:
        # Логируем ошибки чтения CSV
        print(f"Ошибка чтения CSV файла: {e}")
        return []


# Запрашивает логин и пароль через консоль: одни на все серверы или отдельно для каждого
def prompt_for_credentials(servers):
    print("\nКак использовать учетные данные для подключения к iLO?")
    print("  1 - ввести ОДНИ учетные данные для ВСЕГО оборудования")
    print("  2 - вводить учетные данные ОТДЕЛЬНО для каждого оборудования")

    mode = ""
    while mode not in ("1", "2"):
        mode = input("Выберите режим (1/2): ").strip()
        if mode not in ("1", "2"):
            print("Некорректный ввод. Введите 1 или 2.")

    if mode == "1":
        # Одни учетные данные на все серверы
        username = input("Введите логин для всего оборудования: ").strip()
        password = getpass.getpass("Введите пароль для всего оборудования: ")
        for server in servers:
            server['username'] = username
            server['password'] = password
        print(f"Учетные данные установлены для всех {len(servers)} серверов.\n")
    else:
        # Свои учетные данные для каждого сервера
        for index, server in enumerate(servers, 1):
            ip = server['ip']
            print(f"\n[{index}/{len(servers)}] iLO: {ip}")
            server['username'] = input("  Логин: ").strip()
            server['password'] = getpass.getpass("  Пароль: ")
        print(f"\nУчетные данные установлены для всех {len(servers)} серверов.\n")

    return servers


# Обрабатывает данные одного сервера: собирает все ресурсы Redfish
def process_server(server, output_dir):
    ip = server['ip']
    print(f"Обработка сервера {ip} начата")
    # Формируем временную папку с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(output_dir, f"temp_{ip}_{timestamp}")
    os.makedirs(temp_dir, exist_ok=True)
    log_file = os.path.join(temp_dir, "errors.log")
    # Создаем клиент Redfish с прямой авторизацией по логину/паролю
    client = RedfishClient(f"https://{ip}", server['username'], server['password'], log_file, ip)
    # Проверяем инициализацию и авторизацию
    if client.client is None or not client.login():
        print(f"Пропуск сервера {ip} из-за ошибки инициализации или авторизации")
        error_dir = os.path.join(output_dir, f"error_{ip}_{timestamp}")
        os.rename(temp_dir, error_dir)
        print(f"Логи ошибок сохранены в {error_dir}")
        return False
    try:
        # Собираем ВСЕ ресурсы дерева Redfish
        collector = ServerInfoCollector(client)
        server_info_file = os.path.join(temp_dir, "redfish_full.json")
        collector.collect_resources(output_file=server_info_file)

        # Извлекаем серийный номер для имени папки
        serial_number = None
        system_data = collector.collected_data.get("/redfish/v1/Systems/1", {})
        if "SerialNumber" in system_data:
            serial_number = system_data["SerialNumber"].strip()

        # Используем серийный номер или IP для имени папки
        folder_name = serial_number if serial_number else ip

        # Переименовываем временную папку в окончательную
        final_dir = os.path.join(output_dir, f"{folder_name}_{timestamp}")
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
        del client


# Основная функция программы
def main():
    # Константы
    CSV_FILE = "servers.csv"      # Файл со списком iLO (только колонка 'ip')
    OUTPUT_DIR = "server_logs"    # Папка для сохранения логов
    DEFAULT_MAX_WORKERS = 10      # Количество потоков по умолчанию

    # Создаем выходную папку, если она не существует
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Запуск полного сбора ресурсов Redfish (прямая авторизация в iLO)")

    # 1. Читаем список серверов из CSV
    servers = read_servers_from_csv(CSV_FILE)
    if not servers:
        print("Серверы не найдены. Проверьте CSV файл.")
        return
    print(f"Всего серверов для обработки: {len(servers)}")

    # 2. Запрашиваем учетные данные через консоль (в CSV хранится только адрес)
    prompt_for_credentials(servers)

    # 3. Запрашиваем количество одновременных обработок
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

    # 4. Обрабатываем серверы в многопоточном режиме
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

    # 5. Выводим итоговую статистику
    print(f"Обработка завершена: {success_count}/{len(servers)} серверов успешно обработано")
    if failed_servers:
        print(f"Сбой при обработке серверов: {', '.join(failed_servers)}")


# Точка входа программы
if __name__ == "__main__":
    main()
