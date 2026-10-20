import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project_euler_offline.app import ProjectEulerOfflineApp
from project_euler_offline.document_builder import DocumentBuilder
from project_euler_offline.http_document_cache import HttpDocumentCache


class ResourcePathTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.output_path = Path(temporary_directory.name)
        self.app = ProjectEulerOfflineApp()
        self.app._output_path = self.output_path

    def test_resources_are_written_beneath_output_directory(self):
        for url_path, filename in (
            ("resources/images/example.png", "example.png"),
            ("/resources/images/example.png", "example.png"),
            ("resources/images/example.png?v=1", "example.png"),
            ("/resources/images/example.png?v=1", "example.png"),
            ("/resources/images/example.gif?v=1", "example.gif"),
            (
                "/resources/images/0998_SquaringTriangle.jpg?",
                "0998_SquaringTriangle.jpg",
            ),
        ):
            with self.subTest(url_path=url_path):
                with patch.object(
                    self.app, "_retrieve_http_data", return_value=b"resource data"
                ):
                    data, path = self.app._write_http_resource(url_path)

                self.assertEqual(path, self.output_path / "resources/images" / filename)
                self.assertEqual(path.read_bytes(), b"resource data")
                self.assertEqual(data, b"resource data")

    def test_embedded_resources_are_written_in_output_base(self):
        for url_path in (
            "resources/documents/example.txt",
            "/resources/documents/example.txt?v=1",
        ):
            with self.subTest(url_path=url_path):
                with patch.object(
                    self.app, "_retrieve_http_data", return_value=b"problem data"
                ):
                    _, path = self.app._write_http_resource(
                        url_path, store_in_base=True
                    )

                self.assertEqual(path, self.output_path / "example.txt")
                self.assertEqual(path.read_bytes(), b"problem data")

    def test_root_relative_resources_reuse_canonical_http_cache_entries(self):
        self.app._args = SimpleNamespace(base_url="https://projecteuler.net/")
        cache = HttpDocumentCache(self.output_path / "http_cache.sqlite3")
        self.addCleanup(cache._database_connection.close)
        self.app._http_cache = cache
        with cache._database_connection:
            cache._database_connection.execute(
                "INSERT INTO http_cache (request_url, response_data) VALUES (?, ?)",
                ("https://projecteuler.net/resources/images/example.png?v=1", b"image"),
            )

        for url_path in (
            "resources/images/example.png?v=1",
            "/resources/images/example.png?v=1",
        ):
            with self.subTest(url_path=url_path):
                self.assertEqual(
                    self.app._retrieve_http_data(url_path, cache_only=True), b"image"
                )

    def test_graphics_references_use_relative_paths_without_query_strings(self):
        for url_path in (
            "resources/images/example.png",
            "/resources/images/example.png",
            "resources/images/example.png?v=1",
            "/resources/images/example.png?v=1",
        ):
            with self.subTest(url_path=url_path):
                builder = DocumentBuilder(is_spaced=False)
                builder.append_problem_latex_content(
                    rf"\includegraphics[width=5cm]{{{url_path}}}"
                )
                path = builder.write(self.output_path, "example")

                self.assertIn(
                    r"\includegraphics[width=5cm]{resources/images/example.png}",
                    path.read_text(),
                )

    def test_problem_998_image_uses_relative_path_without_empty_query(self):
        builder = DocumentBuilder(is_spaced=False)
        builder.process_problem_html(
            998,
            "<title>#998 Squaring the Triangle - Project Euler</title>"
            '<div class="problem_content">'
            '<img src="/resources/images/0998_SquaringTriangle.jpg?">'
            "</div>",
        )
        path = builder.write(self.output_path, "example")

        self.assertRegex(
            path.read_text(),
            r"\\includegraphics(?:\[[^\]]*\])?"
            r"\{resources/images/0998_SquaringTriangle\.jpg\}",
        )

    def test_root_relative_gifs_keep_matching_original_urls(self):
        for frame_count, expected in (
            (1, r"\includegraphics{resources/images/example.png}"),
            (
                3,
                r"\animategraphics[controls=all,keepaspectratio,loop,width=\linewidth]"
                r"{1}{resources/images/example-}{0}{2}",
            ),
        ):
            with self.subTest(frame_count=frame_count):
                builder = DocumentBuilder(is_spaced=False)
                builder.append_problem_latex_content(
                    r"\includegraphics{/resources/images/example.gif?v=1}"
                )
                builder.process_animated_resources(
                    [
                        {
                            "url_path": "/resources/images/example.gif?v=1",
                            "file_path": Path("resources/images/example.gif"),
                            "frame_count": frame_count,
                        }
                    ]
                )
                path = builder.write(self.output_path, "example")

                self.assertIn(expected, path.read_text())
