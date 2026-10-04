# дз1 по python, банковские счета
# Григорий Смирнов. Части 1 - 3 (то есть, все)

import csv
import json
import re
from datetime import datetime
from pathlib import Path


# даты из файла бывают в разных форматах, перебираем
DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
)

# проверка имени - имя фамилия, с большой буквы (кирилица или лaтиница)
HOLDER_PATTERN = re.compile(
    r"^[A-ZА-ЯЁ][a-zа-яё]+ [A-ZА-ЯЁ][a-zа-яё]+$"
)


class Account:
    _account_counter = 1000  # нумерация счетов с 1000

    def __init__(self, account_holder, balance=0, account_number=None):
        self._validate_holder(account_holder)

        if balance < 0:
            raise ValueError("Начальный баланс не может быть отрицательным")

        self.holder = account_holder.strip()
        # Если номер передали руками (для тестового json) - берем его
        if account_number:
            self.account_number = account_number
        else:
            self.account_number = f"ACC-{Account._account_counter}"
            Account._account_counter += 1

        self._balance = float(balance)
        self.operations_history = []  # сюда падоют все операции

    @staticmethod
    def _validate_holder(name):
        if not name or not HOLDER_PATTERN.match(name.strip()):
            raise ValueError(
                "Имя владельца должно бытьв формате «Имя Фамилия» "
                "(кириллица или латиница, с заглавной буквы)"
            )

    def _add_operation(self, op_type, amount, status):
        # одна запись в истории - словарь, так проще потом читать
        record = {
            "type": op_type,
            "amount": amount,
            "timestamp": datetime.now(),
            "balance_after": self._balance,
            "status": status,
        }
        self.operations_history.append(record)

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self._balance += amount
        self._add_operation("deposit", amount, "success")

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if amount > self._balance:
            # денег нет - пишем fail и выходим
            self._add_operation("withdraw", amount, "fail")
            return False
        self._balance -= amount
        self._add_operation("withdraw", amount, "success")
        return True

    def get_balance(self):
        return self._balance

    def get_history(self):
        # возвращаю копию по сути, только даты в строку для красоты
        result = []
        for op in self.operations_history:
            ts = op["timestamp"]
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = str(ts)
            result.append(
                {
                    "type": op["type"],
                    "amount": op["amount"],
                    "datetime": ts_str,
                    "balance_after": op["balance_after"],
                    "status": op["status"],
                }
            )
        return result

    def show_top_operations(self, n=5):
        # n самых жирных операций по сумме (только success)
        good = [op for op in self.operations_history if op["status"] == "success"]
        good.sort(key=lambda x: x["amount"], reverse=True)
        top = good[:n]

        print(f"\nТоп-{n} операций по сумме (счёт {self.account_number}):")
        for op in top:
            ts = op["timestamp"]
            if isinstance(ts, datetime):
                ts = ts.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  {ts} | {op['type']:10} | {op['amount']:>10.2f} | "
                f"баланс {op['balance_after']:.2f}"
            )
        return top

    @staticmethod
    def _parse_date(date_str):
        if not date_str:
            return None
        date_str = str(date_str).strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                pass  # пробуем следующий формат
        return None

    def clean_history(self, raw_records):
        # выкидываем мусор из файла: опечатки в operation, кривые даты и тд
        allowed = self._allowed_operations()
        cleaned = []

        for row in raw_records:
            # статус должен быть именно success (succes в файле - брак)
            if row.get("status") != "success":
                continue

            operation = row.get("operation")
            if operation not in allowed:
                continue

            amount = row.get("amount")
            if amount is None or amount == "":
                continue
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                continue
            if amount <= 0:
                continue  # отрицательные и нулевые не берем

            dt = self._parse_date(row.get("date"))
            if dt is None:
                continue

            cleaned.append(
                {
                    "type": operation,
                    "amount": amount,
                    "timestamp": dt,
                    "balance_after": float(row.get("balance_after", 0)),
                    "status": "success",
                }
            )

        cleaned.sort(key=lambda x: x["timestamp"])  # по времени
        return cleaned

    def _allowed_operations(self):
        raise NotImplementedError  # переопределяется в наследниках

    def _read_transactions_file(self, filepath):
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {filepath}")

        ext = path.suffix.lower()
        if ext == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        if ext == ".csv":
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    item = dict(row)
                    # в csv пустая сумма приходит как строка
                    if item.get("amount") == "":
                        item["amount"] = None
                    elif item.get("amount") is not None:
                        item["amount"] = float(item["amount"])
                    if item.get("balance_after") not in (None, ""):
                        item["balance_after"] = float(item["balance_after"])
                    rows.append(item)
                return rows

        raise ValueError("только csv или json, остальное не умею")

    def load_history_from_file(self, filepath):
        all_rows = self._read_transactions_file(filepath)

        # в файле все счета вместе, оставляем только наш
        mine = [
            r for r in all_rows
            if r.get("account_number") == self.account_number
            and r.get("account_type") == self.account_type
        ]

        valid = self.clean_history(mine)
        for rec in valid:
            self.operations_history.append(rec)

        if valid:
            # баланс как после последней нормальной операции
            self._balance = valid[-1]["balance_after"]

        return len(valid)


class CheckingAccount(Account):
    account_type = "checking"

    def _allowed_operations(self):
        return {"deposit", "withdraw"}  # процентов тут нет


class SavingsAccount(Account):
    account_type = "savings"

    def _allowed_operations(self):
        return {"deposit", "withdraw", "interest"}

    def apply_interest(self, rate):
        # rate типа 7 значит 7%
        if rate <= 0:
            raise ValueError("Ставка должна быть положительной")
        interest = self._balance * (rate / 100)
        if interest <= 0:
            return 0.0
        self._balance += interest
        self._add_operation("interest", interest, "success")
        return interest

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")

        limit = self._balance * 0.5  # нельзя снять больше половины
        if amount > limit:
            self._add_operation("withdraw", amount, "fail")
            return False

        if amount > self._balance:
            self._add_operation("withdraw", amount, "fail")
            return False

        self._balance -= amount
        self._add_operation("withdraw", amount, "success")
        return True


if __name__ == "__main__":
    print("--- проверка руками (часть 1-2) ---\n")

    checking = CheckingAccount("Grуgory Smirnov", 1000)
    print(f"счёт {checking.account_number}, тип {checking.account_type}")
    checking.deposit(500)
    checking.withdraw(200)
    checking.withdraw(5000)  # должно упасть в fail
    print("баланс:", checking.get_balance())

    savings = SavingsAccount("Иван Петров", 2000)
    savings.apply_interest(7)
    print("после процентов:", savings.get_balance())
    savings.withdraw(1500)  # >50%, не даст
    savings.withdraw(500)
    savings.show_top_operations(3)

    print("\n--- загрузка грязных данных (часть 3) ---\n")

    folder = Path(__file__).resolve().parent
    json_file = folder / "transactions_dirty.json"

    acc1 = CheckingAccount("Gregory Smirnov", 0, account_number="ACC-100001")
    cnt1 = acc1.load_history_from_file(json_file)
    print(f"ACC-100001: записей {cnt1}, баланс {acc1.get_balance()}")

    acc2 = SavingsAccount("Ivan Petrov", 0, account_number="ACC-100002")
    cnt2 = acc2.load_history_from_file(json_file)
    print(f"ACC-100002: записей {cnt2}, баланс {acc2.get_balance()}")

    csv_file = folder / "transactions_dirty.csv"
    acc3 = CheckingAccount("Gregory Smirnov", 0, account_number="ACC-100003")
    cnt3 = acc3.load_history_from_file(csv_file)
    print(f"ACC-100003 (csv): записей {cnt3}, баланс {acc3.get_balance()}")
