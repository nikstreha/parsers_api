import logging
import os
from datetime import datetime

import typer
from gunicorn.app.base import BaseApplication

log_dir = "src/logs"

if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_filename = os.path.join(log_dir, datetime.now().strftime("%Y-%m-%d.%H-%M-%S.log"))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(process)d] [%(levelname)s] [%(pathname)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %z",
    filename=log_filename,
    filemode="a",
)

logging.info("Логирование запущено")
logger = logging.getLogger(__name__)

cli = typer.Typer(no_args_is_help=True)


class StandaloneApplication(BaseApplication):
    def __init__(self, app_uri, options=None):
        self.options = options or {}
        self.app_uri = app_uri
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        from gunicorn.util import import_app

        return import_app(self.app_uri)


@cli.command()
def api(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(8000),
    workers: int = typer.Option(1),
    reload: bool = typer.Option(False),
) -> None:
    options = {
        "bind": f"{host}:{port}",
        "workers": workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "reload": reload,
        "factory": True,
        "loglevel": "info",
        "accesslog": "-",
    }

    logger.info(f"Starting Gunicorn on {host}:{port} with {workers} workers")

    StandaloneApplication("parser_api.composition.api_app:build_api_app", options).run()


if __name__ == "__main__":
    cli()
