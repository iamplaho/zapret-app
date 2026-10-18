"""Точка входа: python main.py (или сборка через zapret-app.spec)."""
from zapret_app import system
from zapret_app.ui import App


def main():
    if not system.acquire_single_instance():
        system.show_message("zapret-app уже запущен. Найдите его значок в трее.")
        return
    App().mainloop()


if __name__ == "__main__":
    main()
