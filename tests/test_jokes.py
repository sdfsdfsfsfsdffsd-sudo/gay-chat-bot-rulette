from __future__ import annotations

import unittest

from bot.jokes import DEFAULT_JOKE_SOURCE_URLS, allowed_joke_source, format_joke_html, parse_jokes_from_html


class JokeParserTests(unittest.TestCase):
    def test_default_rotation_excludes_motustrans(self) -> None:
        self.assertNotIn("https://www.motustrans.ru/forum/forum12/topic3/messages/", DEFAULT_JOKE_SOURCE_URLS)

    def test_parses_anekdotovstreet_paragraphs(self) -> None:
        html = """
        <p>Сборник самых смешных анекдотов. Читайте свежие анекдоты.</p>
        <p>Первый нормальный анекдот про дальнобойщика и трассу.</p>
        <p>Второй нормальный анекдот, где есть завязка и финал.</p>
        """

        jokes = parse_jokes_from_html("https://anekdotovstreet.com/transport/dalnoboyschiki/", html)

        self.assertEqual([joke.text for joke in jokes], [
            "Первый нормальный анекдот про дальнобойщика и трассу.",
            "Второй нормальный анекдот, где есть завязка и финал.",
        ])

    def test_parses_motustrans_forum_posts(self) -> None:
        html = """
        <html><body>
        <a>#1</a>
        03.12.2009 02:42:40
        Сидит дальнобойщик в баре.
        - Финальная строка анекдота.
        <a>#2</a>
        03.12.2009 02:44:00
        Еще один анекдот про трассу и грузовик.
        Страницы: 1
        </body></html>
        """

        jokes = parse_jokes_from_html("https://www.motustrans.ru/forum/forum12/topic3/messages/", html)

        self.assertEqual(len(jokes), 2)
        self.assertIn("Сидит дальнобойщик", jokes[0].text)
        self.assertIn("Еще один анекдот", jokes[1].text)

    def test_blocks_protected_class_joke_sources(self) -> None:
        self.assertFalse(allowed_joke_source("https://tudoy-sudoy.od.ua/ru/blog/anekdoty-pro-evreev/"))
        self.assertFalse(allowed_joke_source("https://anec.xoxma.net/anec/17/"))

    def test_formats_joke_as_safe_html(self) -> None:
        jokes = parse_jokes_from_html(
            "https://example.test/jokes",
            "<p>Анекдот с <опасным> HTML и нормальной длиной текста.</p>",
        )

        formatted = format_joke_html(jokes[0])

        self.assertIn("&lt;опасным&gt;", formatted)
        self.assertNotIn("Источник", formatted)
        self.assertNotIn("href=", formatted)


if __name__ == "__main__":
    unittest.main()
