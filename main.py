from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FORMAT = "%Y-%m-%d"
DATA_FILE = Path("notes.json")


class ValidationError(Exception):
    """Ошибка проверки пользовательского ввода."""


@dataclass
class Note(ABC):
    title: str
    text: str
    tags: list[str]
    date: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.title.strip():
            raise ValidationError("Заголовок не может быть пустым.")
        if not self.text.strip():
            raise ValidationError("Текст заметки не может быть пустым.")
        if not isinstance(self.tags, list):
            raise ValidationError("Теги должны быть списком.")
        for tag in self.tags:
            if not tag.strip():
                raise ValidationError("Тег не может быть пустым.")
        try:
            datetime.strptime(self.date, DATE_FORMAT)
        except ValueError as exc:
            raise ValidationError("Дата должна быть в формате ГГГГ-ММ-ДД.") from exc

    @abstractmethod
    def note_type(self) -> str:
        """Возвращает тип заметки."""

    @abstractmethod
    def display(self) -> str:
        """Полиморфный вывод заметки."""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.note_type()
        return data


@dataclass
class TextNote(Note):
    def note_type(self) -> str:
        return "text"

    def display(self) -> str:
        return (
            f"[Текстовая заметка]\n"
            f"Заголовок: {self.title}\n"
            f"Текст: {self.text}\n"
            f"Теги: {', '.join(self.tags)}\n"
            f"Дата: {self.date}"
        )


@dataclass
class VoiceNote(Note):
    duration_seconds: int = 0

    def validate(self) -> None:
        super().validate()
        if self.duration_seconds < 0:
            raise ValidationError("Длительность голосовой заметки не может быть отрицательной.")

    def note_type(self) -> str:
        return "voice"

    def display(self) -> str:
        return (
            f"[Голосовая заметка]\n"
            f"Заголовок: {self.title}\n"
            f"Описание: {self.text}\n"
            f"Длительность: {self.duration_seconds} сек.\n"
            f"Теги: {', '.join(self.tags)}\n"
            f"Дата: {self.date}"
        )


class UndoStack:
    """Стек для отмены действий."""

    def __init__(self) -> None:
        self._stack: list[list[Note]] = []

    def push(self, notes: list[Note]) -> None:
        # Сохраняем копию состояния списка заметок
        self._stack.append([note_from_dict(note.to_dict()) for note in notes])

    def pop(self) -> list[Note] | None:
        if not self._stack:
            return None
        return self._stack.pop()

    def is_empty(self) -> bool:
        return len(self._stack) == 0


class NotebookOrganizer:
    def __init__(self) -> None:
        self.notes: list[Note] = []
        self.undo_stack = UndoStack()

    def add_note(self, note: Note) -> None:
        self.undo_stack.push(self.notes)
        self.notes.append(note)

    def list_notes(self) -> None:
        if not self.notes:
            print("Заметок пока нет.")
            return

        for index, note in enumerate(self.notes, start=1):
            print(f"\n--- Заметка #{index} ---")
            print(note.display())

    def edit_note(self, index: int, new_note: Note) -> None:
        self._check_index(index)
        self.undo_stack.push(self.notes)
        self.notes[index] = new_note

    def delete_note(self, index: int) -> None:
        self._check_index(index)
        self.undo_stack.push(self.notes)
        deleted = self.notes.pop(index)
        print(f"Удалена заметка: {deleted.title}")

    def filter_by_tag(self, tag: str) -> list[Note]:
        return [note for note in self.notes if tag.lower() in [t.lower() for t in note.tags]]

    def filter_by_date(self, date: str) -> list[Note]:
        self._validate_date(date)
        return [note for note in self.notes if note.date == date]

    def undo(self) -> None:
        previous_state = self.undo_stack.pop()
        if previous_state is None:
            print("Нет действий для отмены.")
            return
        self.notes = previous_state
        print("Последнее действие отменено.")

    def save_to_json(self, file_path: Path = DATA_FILE) -> None:
        for note in self.notes:
            note.validate()

        with file_path.open("w", encoding="utf-8") as file:
            json.dump([note.to_dict() for note in self.notes], file, ensure_ascii=False, indent=4)

        print(f"Заметки сохранены в файл: {file_path}")

    def load_from_json(self, file_path: Path = DATA_FILE) -> None:
        if not file_path.exists():
            print("Файл с заметками не найден. Будет создан новый список заметок.")
            self.notes = []
            return

        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        self.notes = [note_from_dict(item) for item in data]
        print(f"Заметки загружены из файла: {file_path}")

    def _check_index(self, index: int) -> None:
        if index < 0 or index >= len(self.notes):
            raise IndexError("Заметка с таким номером не найдена.")

    @staticmethod
    def _validate_date(date: str) -> None:
        try:
            datetime.strptime(date, DATE_FORMAT)
        except ValueError as exc:
            raise ValidationError("Дата должна быть в формате ГГГГ-ММ-ДД.") from exc


def note_from_dict(data: dict[str, Any]) -> Note:
    note_type = data.get("type", "text")

    if note_type == "text":
        return TextNote(
            title=data["title"],
            text=data["text"],
            tags=data["tags"],
            date=data["date"],
        )

    if note_type == "voice":
        return VoiceNote(
            title=data["title"],
            text=data["text"],
            tags=data["tags"],
            date=data["date"],
            duration_seconds=int(data.get("duration_seconds", 0)),
        )

    raise ValidationError(f"Неизвестный тип заметки: {note_type}")


def input_date(prompt: str = "Дата (ГГГГ-ММ-ДД, Enter = сегодня): ") -> str:
    value = input(prompt).strip()
    if not value:
        return datetime.now().strftime(DATE_FORMAT)

    datetime.strptime(value, DATE_FORMAT)
    return value


def input_tags() -> list[str]:
    raw_tags = input("Теги через запятую: ").strip()
    tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    if not tags:
        raise ValidationError("Нужен хотя бы один тег.")
    return tags


def create_note_from_input() -> Note:
    print("\nВыберите тип заметки:")
    print("1. Текстовая")
    print("2. Голосовая")

    note_type = input("Ваш выбор: ").strip()
    title = input("Заголовок: ").strip()
    text = input("Текст/описание: ").strip()
    tags = input_tags()
    date = input_date()

    if note_type == "1":
        return TextNote(title=title, text=text, tags=tags, date=date)

    if note_type == "2":
        duration = int(input("Длительность в секундах: ").strip())
        return VoiceNote(title=title, text=text, tags=tags, date=date, duration_seconds=duration)

    raise ValidationError("Некорректный тип заметки.")


def print_notes(notes: list[Note]) -> None:
    if not notes:
        print("Ничего не найдено.")
        return

    for index, note in enumerate(notes, start=1):
        print(f"\n--- Результат #{index} ---")
        print(note.display())


def print_menu() -> None:
    print("\n========== Notebook Organizer ==========")
    print("1. Создать заметку")
    print("2. Показать все заметки")
    print("3. Редактировать заметку")
    print("4. Удалить заметку")
    print("5. Фильтр по тегу")
    print("6. Фильтр по дате")
    print("7. Отменить последнее действие")
    print("8. Сохранить в JSON")
    print("9. Загрузить из JSON")
    print("0. Выход")


def main() -> None:
    app = NotebookOrganizer()
    app.load_from_json()

    while True:
        try:
            print_menu()
            choice = input("Выберите действие: ").strip()

            if choice == "1":
                note = create_note_from_input()
                app.add_note(note)
                print("Заметка создана.")

            elif choice == "2":
                app.list_notes()

            elif choice == "3":
                app.list_notes()
                index = int(input("Номер заметки для редактирования: ")) - 1
                new_note = create_note_from_input()
                app.edit_note(index, new_note)
                print("Заметка отредактирована.")

            elif choice == "4":
                app.list_notes()
                index = int(input("Номер заметки для удаления: ")) - 1
                app.delete_note(index)

            elif choice == "5":
                tag = input("Введите тег: ").strip()
                print_notes(app.filter_by_tag(tag))

            elif choice == "6":
                date = input_date("Введите дату для фильтрации (ГГГГ-ММ-ДД): ")
                print_notes(app.filter_by_date(date))

            elif choice == "7":
                app.undo()

            elif choice == "8":
                app.save_to_json()

            elif choice == "9":
                app.load_from_json()

            elif choice == "0":
                app.save_to_json()
                print("Выход из программы.")
                break

            else:
                print("Некорректный пункт меню.")

        except (ValidationError, ValueError, IndexError) as error:
            print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
