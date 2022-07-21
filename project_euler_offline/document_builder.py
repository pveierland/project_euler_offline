import re
from collections import defaultdict
from pathlib import Path
from string import Template

import pandoc
import pandoc.types
from bs4 import BeautifulSoup

LATEX_BLOCK_STYLES = {
    "center": {
        "pre": r"\begin{center}",
        "post": r"\end{center}",
    },
    "margin_left": {
        "pre": r"\begin{center}",
        "post": r"\end{center}",
    },
}

LATEX_CHARACTER_SUBSTITUTIONS = {
    "’": r"\textquoteright{}",
    "⌈": r"\ensuremath{⌈}",
    "⌉": r"\ensuremath{⌉}",
    "⌊": r"\ensuremath{⌊}",
    "⌋": r"\ensuremath{⌋}",
    "↔": r"\ensuremath{↔}",
    "∅": r"\ensuremath{∅}",
    "∈": r"\ensuremath{∈}",
    "∑": r"\ensuremath{∑}",
    "≠": r"\ensuremath{≠}",
    "∩": r"\ensuremath{∩}",
    "≈": r"\ensuremath{≈}",
    "≡": r"\ensuremath{≡}",
    "≤": r"\ensuremath{≤}",
    "≥": r"\ensuremath{≥}",
    "⋅": r"\ensuremath{⋅}",
    "①": r"\circled{1}",
    "⑩": r"\circled{10}",
    "⑪": r"\circled{11}",
    "②": r"\circled{2}",
    "③": r"\circled{3}",
    "④": r"\circled{4}",
    "⑤": r"\circled{5}",
    "⑥": r"\circled{6}",
    "⑦": r"\circled{7}",
    "⑧": r"\circled{8}",
    "⑨": r"\circled{9}",
    "ń": r"\'{n}",
    "μ": r"\ensuremath{μ}",
    "π": r"\ensuremath{π}",
    "ω": r"\ensuremath{ω}",
}

LATEX_INLINE_STYLES = {
    "blue": {
        "pre": r"{\color{blue}",
        "post": r"}",
    },
    "green": {
        "pre": r"{\color{green}",
        "post": r"}",
    },
    "italic": {
        "pre": r"\textit{",
        "post": r"}",
    },
    "larger": {
        "pre": r"{\large{}",
        "post": r"}",
    },
    "largest": {
        "pre": r"{\Large{}",
        "post": r"}",
    },
    "monospace": {
        "pre": r"\texttt{",
        "post": r"}",
    },
    "orange": {
        "pre": r"{\color{orange}",
        "post": r"}",
    },
    "red": {
        "pre": r"{\color{red}",
        "post": r"}",
    },
    "smaller": {
        "pre": r"{\small{}",
        "post": r"}",
    },
    "smallest": {
        "pre": r"{\footnotesize{}",
        "post": r"}",
    },
    "strong": {
        "pre": r"\textbf{",
        "post": r"}",
    },
    "underline": {
        "pre": r"\underline{",
        "post": r"}",
    },
}

LATEX_TEXTATTACHFILE_LINK_COLOR = "linkcolor"


def extract_page_title(soup):
    for header_type in range(1, 6 + 1):
        header = soup.find(f"h{header_type}")
        if header:
            return header.extract()


class DocumentBuilder:
    def __init__(self, is_spaced):
        self._is_spaced = is_spaced

        self._color_mappings = {}
        self._classes = defaultdict(list)
        self._url_paths_about = set()
        self._url_paths_embedded = set()
        self._url_paths_resources = set()

        self._output_latex_content = ""
        self._output_html_debug = ""
        self._output_has_appendix = False

    def _build_latex_preamble(self):
        output_latex_preamble = ""

        for color_value, color_name in self._color_mappings.items():
            output_latex_preamble += (
                f"\definecolor{{{color_name}}}{{HTML}}{{{color_value}}}\n"
            )

        return output_latex_preamble

    def _transform_html_tag_class_info(self, soup, tag):
        for block_tag_name in ["p", "blockquote"]:
            block_tags = [
                block_tag
                for block_tag in tag.find_all(block_tag_name)
                if block_tag.get("class") or block_tag.get("style")
            ]

            for block_tag in block_tags:
                # Add class info to wrapped div to make it available in pandoc structure:
                classes = set(
                    block_tag.get("class", [])
                ) | self._transform_style_to_classes(block_tag.get("style", ""))

                if classes:
                    block_tag.wrap(soup.new_tag("div", attrs={"class": list(classes)}))

        for span_tag in tag.find_all("span"):
            if style := span_tag.get("style"):
                # Add class info to span to make it available in pandoc structure:
                span_tag["class"] = list(
                    set(span_tag.get("class", []))
                    | self._transform_style_to_classes(style)
                )

        return tag

    def _transform_html_to_latex(self, content_html):
        latex_substitutions = {}

        def replace_with_marker(match):
            marker_index = len(latex_substitutions)
            marker = f"LATEX-{marker_index}-SUBSTITUTION"
            latex_substitutions[marker] = match.group(0)
            return marker

        content_html = re.sub(r"\$\$[^$]+?\$\$", replace_with_marker, content_html)
        content_html = re.sub(r"\$[^$]+?\$", replace_with_marker, content_html)
        content_html = re.sub(
            r"\\\[.*?\\\]",
            replace_with_marker,
            content_html,
            flags=re.DOTALL | re.MULTILINE,
        )

        document_pandoc = pandoc.read(content_html, format="html")
        self._transform_pandoc_document(document_pandoc)
        document_latex = str(pandoc.write(document_pandoc, format="latex").strip())

        for marker, substitution in latex_substitutions.items():
            substitution = substitution.replace("&amp;", r"&")
            substitution = substitution.replace("&lt;", r"<")
            substitution = substitution.replace("&gt;", r">")
            document_latex = document_latex.replace(marker, substitution)

        # Prevent issue with align environement wrapped in math env:
        document_latex = re.sub(
            r"((\$\$?)|(\\\[))\s*(?P<begin_env>\\begin{((align(ed)?)|equation)\*?})",
            "\g<begin_env>",
            document_latex,
            flags=re.DOTALL | re.MULTILINE,
        )
        document_latex = re.sub(
            r"(?P<end_env>\\end{((align(ed)?)|equation)\*?})\s*((\$\$?)|(\\\]))",
            "\g<end_env>",
            document_latex,
            flags=re.DOTALL | re.MULTILINE,
        )

        # Ensure non-numbered align and equation envs:
        document_latex = re.sub(
            r"\\(?P<begin_end>(begin|end)){(?P<env_type>(align|equation))}",
            "\\\\\g<begin_end>{\g<env_type>*}",
            document_latex,
        )

        # Set solo image centering:
        document_latex = re.sub(
            r"(?P<space_pre>\s\s+)\\includegraphics(?P<options>\[[^\]]*\])?{(?P<name>.*?)}(\\\\)?(?P<space_post>\s\s+)",
            r"\g<space_pre>\\begin{center}\\includegraphics\g<options>{\g<name>}\\end{center}\g<space_post>",
            document_latex,
            flags=re.DOTALL | re.MULTILINE,
        )

        return document_latex

    def _transform_pandoc_document(self, document):
        self._transform_pandoc_document_inline_elements(document)
        self._transform_pandoc_document_block_elements(document)

    def _transform_pandoc_document_block_elements(self, document):
        def match_block_classes(elt, path):
            if isinstance(elt, (pandoc.types.Para, pandoc.types.Plain)):
                for parent, _ in path[::-1]:
                    if isinstance(parent, pandoc.types.Div):
                        return parent[0][1]
                    elif isinstance(parent, (pandoc.types.Para, pandoc.types.Plain)):
                        break
                    elif not isinstance(parent, (pandoc.types.BlockQuote, list)):
                        break

        matches = [
            (elt, path, classes)
            for (elt, path) in pandoc.iter(document, path=True)
            if (classes := match_block_classes(elt, path))
        ]

        for elt, _, classes in reversed(matches):
            for cls in classes:
                if transform := LATEX_INLINE_STYLES.get(cls):
                    if post := transform.get("post"):
                        elt[0].append(pandoc.types.RawInline("latex", post))

                    if pre := transform.get("pre"):
                        elt[0].insert(0, pandoc.types.RawInline("latex", pre))

            for cls in classes:
                if transform := LATEX_BLOCK_STYLES.get(cls):
                    if post := transform.get("post"):
                        elt[0].append(pandoc.types.RawInline("latex", post))

                    if pre := transform.get("pre"):
                        elt[0].insert(0, pandoc.types.RawInline("latex", pre))

    def _transform_pandoc_document_inline_elements(self, document):
        def match_inline_classes(elt, path):
            if isinstance(elt, pandoc.types.Span):
                return elt[0][1]

        matches = [
            (elt, path, classes)
            for (elt, path) in pandoc.iter(document, path=True)
            if (classes := match_inline_classes(elt, path))
        ]

        for elt, _, classes in reversed(matches):
            for cls in classes:
                if transform := LATEX_INLINE_STYLES.get(cls):
                    if post := transform.get("post"):
                        elt[1].append(pandoc.types.RawInline("latex", post))

                    if pre := transform.get("pre"):
                        elt[1].insert(0, pandoc.types.RawInline("latex", pre))
                elif cls.startswith("__COLOR__"):
                    color = cls.removeprefix("__COLOR__")

                    if color in self._color_mappings:
                        color_name = self._color_mappings[color]
                    else:
                        color_name = f"CustomColor{len(self._color_mappings)}"
                        self._color_mappings[color] = color_name

                    elt[1].append(pandoc.types.RawInline("latex", "}"))
                    elt[1].insert(
                        0, pandoc.types.RawInline("latex", f"{{\\color{{{color_name}}}")
                    )

    def _transform_style_to_classes(self, style):
        classes = set()

        style_lower = style.lower()

        if color := re.match("color:\s*#?(?P<color_value>[^;\s]+)", style_lower):
            classes.add(f"__COLOR__{color.group('color_value')}")

        if re.search("font-family:[^;]*(courier new|monospace)", style_lower):
            classes.add("monospace")

        if re.search("font-size:\s*larger", style_lower):
            classes.add("larger")

        if re.search("font-size:\s*smaller", style_lower):
            classes.add("smaller")

        if re.search("font-style:\s*italic", style_lower):
            classes.add("italic")

        if re.search("font-weight:\s*bold", style_lower):
            classes.add("strong")

        if re.search("text-align:\s*center", style_lower):
            classes.add("center")

        if re.search("text-decoration:\s*underline", style_lower):
            classes.add("underline")

        return classes

    def append_about_latex_content(self, about_content_latex):
        if not self._output_has_appendix:
            self._output_has_appendix = True
            self.append_latex_content(
                r"""\titleformat{\section}
{\Large\bfseries\sffamily\color{titleblue}}
{\StyledTitleBox{Appendix}}
{0pt}
{\TitleUnderline{\enspace{}#1}}
\appendix
"""
            )

        self.append_latex_content_page(about_content_latex)
        self.append_latex_content("\n\n")

    def append_latex_content(self, latex_content):
        self.parse_latex_links(latex_content)
        self._output_latex_content += latex_content

    def append_latex_content_page(self, latex_content):
        if self._is_spaced:
            self.append_latex_content("\n\\newpage\n\n")

        self.append_latex_content(latex_content)

    def append_problem_latex_content(self, problem_content_latex):
        self.append_latex_content_page(problem_content_latex)
        self.append_latex_content("\n\n")

    def parse_latex_links(self, content):
        for graphics_match in re.finditer(
            r"\\includegraphics(\[[^\]]*\])?{(?P<path>[^}]+)}", content
        ):
            graphics_path = graphics_match.group("path")
            self._url_paths_resources.add(graphics_path)

        for href_match in re.finditer(
            r"\\href{(?P<href_target>[^}]+)}{(?P<href_label>[^}]+)}", content
        ):
            href_target = href_match.group("href_target")

            if href_target.endswith(".txt"):
                self._url_paths_embedded.add(href_target)
            elif href_target.startswith("about="):
                self._url_paths_about.add(href_target)

    def parse_problem_html_soup(self, soup, problem_id):
        for tag in soup.find_all():
            classes = tag.get("class", [])

            for class_ in classes:
                self._classes[class_].append(problem_id)

    def process_about_html(self, about_url_path, about_html):
        about_soup = BeautifulSoup(about_html, "html.parser")
        about_content_tag = about_soup.find(id="about_page")

        about_title = re.sub(
            "About...\s*(?P<about_title>.*)",
            r"\g<about_title>",
            extract_page_title(about_content_tag).text,
        )

        about_content_latex = (
            rf"\section[Appendix: {about_title}]{{{about_title}}}\n"
            + rf"\label{{sec:{about_url_path}}}\n\n"
            + self._transform_html_to_latex(str(about_content_tag))
        )

        self.append_latex_content_page(about_content_latex)

    def process_animated_resources(self, animated_resources):
        animated_resource_lookup = {
            animated_resource["url_path"]: animated_resource
            for animated_resource in animated_resources
        }

        def transform_animated_resource(match):
            if animated_resource := animated_resource_lookup.get(match.group("path")):
                if animated_resource["frame_count"] != 1:
                    # TODO: Consider getting actual frame rate from source
                    frame_rate = 1

                    file_path_base_name = (
                        str(animated_resource["file_path"].with_suffix("")) + "-"
                    )

                    options = r"controls=all,keepaspectratio,loop,width=\linewidth"

                    if existing_options := match.group("options"):
                        options += "," + existing_options

                    return rf"\animategraphics[{options}]{{{frame_rate}}}{{{file_path_base_name}}}{{0}}{{{animated_resource['frame_count'] - 1}}}"
                else:
                    file_path_png = animated_resource["file_path"].with_suffix(".png")
                    return rf"\includegraphics{{{file_path_png}}}"
            else:
                return match.group(0)

        self._output_latex_content = re.sub(
            r"\\includegraphics(\[(?P<options>[^\]]*)\])?{(?P<path>[^}]+)}",
            transform_animated_resource,
            self._output_latex_content,
        )

    def process_problem_html(self, problem_id, problem_html):
        problem_soup = BeautifulSoup(problem_html, "html.parser")
        problem_content_soup_tag = problem_soup.find(class_="problem_content")

        self.parse_problem_html_soup(problem_content_soup_tag, problem_id)
        problem_content_soup_tag = self._transform_html_tag_class_info(
            problem_soup, problem_content_soup_tag
        )
        problem_content_html = str(problem_content_soup_tag)

        title_match = re.match(
            "^#(?P<problem_id>\d+)\s+(?P<problem_name>.*?) - Project Euler$",
            problem_soup.title.text,
        )
        problem_title = f"{title_match.group('problem_name')}"

        # TODO: Problem ID in section numbering should be explicit
        # TODO: Problem title should link to problem URL
        problem_content_latex = (
            f"\\section[Problem \#{problem_id}: {problem_title}]{{{problem_title}}}\n"
            + f"\\label{{sec:problem_{problem_id}}}\n\n"
            + self._transform_html_to_latex(problem_content_html)
        )

        self.append_problem_latex_content(problem_content_latex)

        self._output_html_debug += f"<!-- Problem {problem_id} -->\n\n"
        self._output_html_debug += problem_content_html + "\n\n"

    def write(self, output_path, build_name):
        output_latex_content = self._output_latex_content

        # Resolve internal embedded files:
        output_latex_content = re.sub(
            r"\\href{(?P<href_url_path_base>[^\s}]*?)(?P<href_filename>[^\/}]*?.txt)}{(?P<href_label>[^}]*?)}",
            rf"\\textattachfile[color={LATEX_TEXTATTACHFILE_LINK_COLOR}]{{\g<href_filename>}}{{\g<href_label>}}\\footnote{{Source: \\url{{https://projecteuler.net/\g<href_url_path_base>\g<href_filename>}}}}",
            output_latex_content,
            flags=re.DOTALL | re.MULTILINE,
        )

        output_latex_content = re.sub(
            r"""\s*\(right\s+click\s+and\s+['"]Save\s+Link/Target\s+As...['"]\)\s*""",
            "",
            output_latex_content,
            flags=re.DOTALL | re.MULTILINE,
        )

        # Resolve internal problem links:
        output_latex_content = re.sub(
            r"\\href{problem=(?P<problem_id>\d+)}{(?P<href_target>[^}]*?)}",
            r"\\hyperref[sec:problem_\g<problem_id>]{\g<href_target>}",
            output_latex_content,
            flags=re.DOTALL | re.MULTILINE,
        )

        # Resolve internal about links:
        output_latex_content = re.sub(
            r"\\href{about=(?P<about_id>[^}]+)}{(?P<href_target>[^}]*?)}",
            lambda x: rf"\hyperref[sec:about={x.group('about_id')}]{{{x.group('href_target')}}}",
            output_latex_content,
            flags=re.DOTALL | re.MULTILINE,
        )

        template_path = Path(__file__).parent / "template.tex"
        template = Template(template_path.read_text())

        output_latex = template.substitute(
            preamble=self._build_latex_preamble(),
            content=output_latex_content,
        )

        for character, substitution in LATEX_CHARACTER_SUBSTITUTIONS.items():
            output_latex = output_latex.replace(character, substitution)

        output_latex_path = output_path / (build_name + ".tex")
        output_latex_path.write_text(output_latex)

        (output_path / "debug_classes.txt").write_text(
            str(sorted(self._classes.keys()))
            + "\n"
            + "\n".join(
                f"{k}: " + ", ".join(map(str, v)) for k, v in self._classes.items()
            )
        )

        (output_path / "debug_output.html").write_text(self._output_html_debug)

        return output_latex_path
