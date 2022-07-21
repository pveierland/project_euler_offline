import argparse
import asyncio
import logging
import subprocess
from pathlib import Path

import pydash
from bs4 import BeautifulSoup
from tqdm import tqdm

from project_euler_offline.document_builder import DocumentBuilder
from project_euler_offline.http_document_cache import (
    HttpDocumentCache,
    MissingDataError,
)

logger = logging.getLogger(__name__)


class ProjectEulerOfflineApp:
    COMMANDS = ["fetch", "render"]

    def _retrieve_http_data(self, url_path, **kwargs):
        return asyncio.run(
            self._http_cache.retrieve_data(self._args.base_url + url_path, **kwargs)
        )

    def _write_http_resource(self, url_path, store_in_base=False, **kwargs):
        data = self._retrieve_http_data(url_path, **kwargs)
        path = self._output_path / (
            Path(url_path).name if store_in_base else Path(url_path)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data, path

    def command_fetch(self):
        problem_ids = list(self.iterate_problem_ids())

        if problem_ids:
            for problem_id in problem_ids:
                try:
                    self.retrieve_problem_html(
                        problem_id,
                        cache_only=self._args.cache_only,
                        force=self._args.force,
                    )
                except MissingDataError:
                    logger.error(f"failed to retrieve problem #{problem_id}")
        else:
            recent_problems_html = self._retrieve_http_data(
                "recent", cache_disable=True
            ).decode("utf8")
            recent_problems_parsed = BeautifulSoup(recent_problems_html, "html.parser")
            recent_problem_id_tags = recent_problems_parsed.find(
                id="problems_table"
            ).find_all(class_="id_column")

            if recent_problem_id_tags:
                latest_problem_id = max(
                    int(recent_problem_id_tag.text)
                    for recent_problem_id_tag in recent_problem_id_tags[1:]
                )

                for problem_id in tqdm(
                    range(1, latest_problem_id + 1), desc="Fetching problem data..."
                ):
                    try:
                        self._retrieve_http_data(f"problem={problem_id}")
                    except MissingDataError:
                        logger.error(f"failed to retrieve problem #{problem_id}")

    def command_render(self):
        document_builder = DocumentBuilder(is_spaced=self._args.spaced)

        problem_id = None
        problem_ids = list(self.iterate_problem_ids())
        problem_count = len(problem_ids) if problem_ids else None

        explicit_problem_ids = bool(problem_ids)

        with tqdm(desc="Rendering problems...", total=problem_count) as progress_bar:
            while not explicit_problem_ids or problem_ids:
                if explicit_problem_ids:
                    problem_id = problem_ids.pop(0)
                elif problem_id is None:
                    problem_id = 1
                else:
                    problem_id += 1

                source_mod_path = (
                    Path(__file__).parent / "../source_mods" / f"{problem_id}.tex"
                )

                if source_mod_path.exists():
                    source_mod_latex = source_mod_path.read_text()
                    document_builder.append_problem_latex_content(source_mod_latex)
                else:
                    # Intentionally only check cache, as we wish to receive None when there are no more problems:
                    problem_data = self._retrieve_http_data(
                        f"problem={problem_id}", cache_only=True
                    )

                    if not problem_data:
                        break

                    problem_html = problem_data.decode("utf8")
                    document_builder.process_problem_html(problem_id, problem_html)

                progress_bar.update(1)

        for about_url_path in tqdm(
            document_builder._url_paths_about, "Rendering appendixes..."
        ):
            source_mod_path = (
                Path(__file__).parent
                / "../source_mods"
                / f"{pydash.snake_case(about_url_path)}.tex"
            )

            if source_mod_path.exists():
                source_mod_latex = source_mod_path.read_text()
                document_builder.append_about_latex_content(source_mod_latex)
            else:
                about_html = self._retrieve_http_data(
                    about_url_path,
                    cache_only=self._args.cache_only,
                    force=self._args.force,
                ).decode("utf8")

                document_builder.process_about_html(about_url_path, about_html)

        animated_resources = []

        for resource_url_path in tqdm(
            document_builder._url_paths_resources, "Processing resources..."
        ):
            _, resource_file_path = self._write_http_resource(
                resource_url_path,
                store_in_base=False,
                cache_only=self._args.cache_only,
                force=self._args.force,
            )

            if resource_file_path.suffix == ".gif":
                gif_frame_count = int(
                    subprocess.run(
                        ["identify", "-format", r"%n\n", str(resource_file_path)],
                        capture_output=True,
                        text=True,
                    ).stdout.splitlines()[0]
                )

                subprocess.run(
                    [
                        "convert",
                        "-coalesce",
                        "-despeckle",
                        str(resource_file_path),
                        str(resource_file_path.with_suffix(".png")),
                    ]
                )

                animated_resources.append(
                    dict(
                        url_path=resource_url_path,
                        file_path=resource_file_path.relative_to(self._output_path),
                        frame_count=gif_frame_count,
                    )
                )

        for embed_url_path in document_builder._url_paths_embedded:
            self._write_http_resource(
                embed_url_path,
                store_in_base=True,
                cache_only=self._args.cache_only,
                force=self._args.force,
            )

        document_builder.process_animated_resources(animated_resources)

        for source_file_path in list(Path(__file__).parent.glob("*.tex")) + list(
            Path(__file__).parent.glob("*.sty")
        ):
            symlink_file_path = self._output_path / source_file_path.name

            if not symlink_file_path.exists():
                symlink_file_path.symlink_to(source_file_path)

        build_name = "project_euler_offline" + ("_spaced" if self._args.spaced else "")
        output_latex_path = document_builder.write(self._output_path, build_name)

        if self._args.pdf:
            subprocess.run(
                [
                    "latexmk",
                    "-pdf",
                    str(output_latex_path.relative_to(self._output_path)),
                ],
                cwd=str(self._output_path),
            )

    def iterate_problem_ids(self):
        if self._args.problems:
            for problem_group in self._args.problems.split(","):
                if "-" in problem_group:
                    problem_start, problem_end = map(
                        int, map(str.strip, problem_group.split("-"))
                    )
                    for problem_id in range(problem_start, problem_end + 1):
                        yield problem_id
                else:
                    yield int(problem_group)

    def run(self):
        parser = argparse.ArgumentParser(
            description="Project Euler Offline (Unofficial)"
        )
        parser.add_argument("--base_url", type=str, default="https://projecteuler.net/")
        parser.add_argument("--cache_only", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--output_path", type=str, default="out")
        parser.add_argument("--pdf", action="store_true")
        parser.add_argument("--problems", type=str)
        parser.add_argument("--spaced", action="store_true")
        parser.add_argument("command", choices=self.COMMANDS)

        self._args = parser.parse_args()
        self._output_path = Path(self._args.output_path)

        self._http_cache = HttpDocumentCache(self._output_path / "http_cache.sqlite3")

        if self._args.command == "fetch":
            self.command_fetch()
        elif self._args.command == "render":
            self.command_render()
