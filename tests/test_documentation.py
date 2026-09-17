from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links_resolve(self):
        files = [ROOT / "README.md"]
        for relative in ("docs", "demos", ".claude"):
            files.extend((ROOT / relative).rglob("*.md"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
                if target.startswith(("https://", "http://", "#", "mailto:")):
                    continue
                file_part = target.split("#", 1)[0]
                with self.subTest(file=str(path.relative_to(ROOT)), link=target):
                    self.assertTrue((path.parent / file_part).exists(), target)

    def test_skill_and_grader_have_project_local_frontmatter(self):
        paths = [ROOT / ".claude" / "skills" / "interview-lab" / "SKILL.md",
                 ROOT / ".claude" / "agents" / "interview-grader.md"]
        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                frontmatter = text.split("---", 2)[1]
                self.assertRegex(frontmatter, r"(?m)^name:\s*[-a-z]+\s*$")
                self.assertRegex(frontmatter, r"(?m)^description:\s*.+$")
                self.assertNotIn("isolation: worktree", frontmatter)
                self.assertNotIn("memory:", frontmatter)

    def test_behavior_checklist_covers_central_sources(self):
        text = (ROOT / "docs" / "source-to-design.md").read_text(encoding="utf-8")
        for link in ("https://blog.janestreet.com/interviewing-at-jane-street/",
                     "https://blog.janestreet.com/what-a-jane-street-dev-interview-is-like/",
                     "https://www.janestreet.com/mock-interview/"):
            self.assertIn(link, text)
        self.assertIn("not claims that a", text)
        self.assertIn("personality", text)
        self.assertIn("No fresh grader", text)
