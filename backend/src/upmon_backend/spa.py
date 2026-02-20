from pathlib import Path

from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    def __init__(self, directory: str | Path) -> None:
        super().__init__(directory=directory, html=True)
        self._spa_directory = Path(directory)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response
