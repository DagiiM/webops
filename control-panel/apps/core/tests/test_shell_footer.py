"""The shell: account, notifications and appearance live in the sidebar footer, not in the page header."""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()
STATIC = Path(settings.BASE_DIR) / "static" / "js"


def section(html, start_pattern, end_tag):
    m = re.search(start_pattern, html)
    assert m, start_pattern
    return html[m.start():html.index(end_tag, m.start())]


@override_settings(ALLOWED_HOSTS=["testserver"])
class ShellFooterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya", "maya@example.com", "pw-123456-x")
        self.client.force_login(self.user)

    def page(self):
        r = self.client.get("/", secure=True)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_footer_holds_account_notifications_and_appearance_once_each(self):
        html = self.page()
        footer = section(html, r'<div class="webops-sidebar-footer"', "</aside>")
        for needle in ('id="userMenuTrigger"', 'id="notificationsToggle"', 'id="appearanceTrigger"', 'id="userDropdown"', 'id="appearanceMenu"'):
            self.assertEqual(html.count(needle), 1, needle)
            self.assertIn(needle, footer, needle)

    def test_the_page_header_carries_none_of_them(self):
        header = section(self.page(), r'<header class="webops-header"', "</header>")
        for needle in ("userMenuTrigger", "notificationsToggle", "appearanceTrigger", "ui-usertrigger", "ui-avatar", "webops-header__actions"):
            self.assertNotIn(needle, header, needle)
        self.assertIn('id="sidebar-toggle"', header)                  # the phone menu button
        self.assertIn("webops-header__brand", header)

    def test_account_menu_shows_who_you_are_and_adapts_to_role(self):
        html = self.page()
        self.assertIn("maya@example.com", html)
        self.assertIn("Sign out", html)
        self.assertNotIn("Branding", section(html, r'id="userDropdown"', 'id="appearanceMenu"'))
        self.assertNotIn("Admin panel", html)
        staff = User.objects.create_user("op", "", "pw-123456-x", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        html = self.page()
        self.assertIn("Signed in", html)                              # no email on file
        self.assertIn("Branding", html)
        self.assertIn("Admin panel", html)

    def test_collapse_control_uses_the_panel_icon_and_is_labelled(self):
        html = self.page()
        button = section(html, r'<button type="button" id="btn-toggle-sidebar"', "</button>")
        self.assertIn("left_panel_close", button)
        self.assertNotIn("first_page", html)
        self.assertIn('aria-label="Collapse sidebar"', button)
        self.assertIn('aria-controls="sidebar"', button)

    def test_footer_menus_are_keyboard_wired_through_the_shared_menu_script(self):
        html = self.page()
        self.assertEqual(html.count("data-ui-menu"), 2)               # account + appearance
        self.assertIn('role="menu"', section(html, r'id="userDropdown"', 'id="appearanceMenu"'))

    def test_no_inline_script_or_style_in_the_footer(self):
        footer = section(self.page(), r'<div class="webops-sidebar-footer"', "</aside>")
        self.assertNotRegex(footer, r"\sstyle=|\sonclick=|<script")

    def test_sign_in_page_has_no_footer(self):
        self.client.logout()
        self.assertNotIn("webops-sidebar-footer", self.client.get("/auth/login/", secure=True).content.decode())


class ShellScriptsTests(TestCase):
    def test_icon_set_knows_both_collapse_icons(self):
        icons = (STATIC / "icons.js").read_text()
        for name in ("panel-left-close", "panel-left-open"):
            self.assertIn(f'"{name}":"<rect', icons)
        self.assertIn('"left_panel_close":"panel-left-close"', icons)
        self.assertIn('"left_panel_open":"panel-left-open"', icons)

    def test_collapse_script_swaps_the_icon_with_the_state(self):
        js = (STATIC / "ui-shell.js").read_text()
        self.assertIn("left_panel_open", js)
        self.assertIn("left_panel_close", js)

    def test_notifications_script_wires_the_button_the_footer_ships(self):
        js = (STATIC / "notifications-center.js").read_text()
        self.assertIn("The sidebar footer ships the button", js)
