from pathlib import Path

from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    def __init__(self, directory: str | Path) -> None:
        super().__init__(directory=directory, html=True)
        self._directory = Path(directory)

    async def get_response(self, path: str, scope):
        full_path, stat_result = self.lookup_path(path)
        if stat_result is None:
            return await super().get_response("index.html", scope)
        return await super().get_response(path, scope)
