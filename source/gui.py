import dearpygui.dearpygui as dpg
import logging

from AO3 import Work
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from . import constants, utils
from .engine import Engine
from .configuration import Configuration

LOG = logging.getLogger(__name__)


def display_rate_limiting_error():
    dpg.create_context()
    dpg.create_viewport(title="Error", width=200, height=100, resizable=False)
    dpg.setup_dearpygui()
    with dpg.window(label="ao3d", tag="primary_window"):
        dpg.add_text("Hit rate limit :(\nPlease try again later.")
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


class GUI:
    engine: Engine

    _work_ids: Set[int]
    _downloaded: Set[int]

    def __init__(self, engine: Engine):
        self.engine = engine
        self._work_ids = set()
        self._downloaded = set()

    def _set_status_text_conditionally(
        self,
        tag: str,
        result: int,
        success_text: str,
        error_text: str,
        success_color: Tuple[int, int, int] = (0, 255, 0),
        error_color: Tuple[int, int, int] = (255, 0, 0),
    ):
        """Utility function for setting a text item.

        If result is 0, set the text to `success_text` and the color to
        `success_color`. Otherwise, set the text to `error_text` and the color 
        to `error_color`.
        """
        color = error_color
        text = error_text
        if result == 0:
            color = success_color
            text = success_text
        dpg.set_value(tag, text)
        dpg.configure_item(tag, color=color, show=True)

    def _login(self, sender=None, data=None) -> None:
        """Callback for clicking the login button.

        Calls the login function on the engine and displays the status.
        """
        dpg.configure_item("login_status_text", color=(255, 255, 0), show=True)
        dpg.set_value("login_status_text", "Logging in...")

        username = dpg.get_value("username_input")
        password = dpg.get_value("password_input")

        result = self.engine.login(username, password)
        self._set_status_text_conditionally(
            "login_status_text",
            result,
            f"Logged in as: {self.engine.session.username}",
            "Login error",
        )

    def _logout(self, sender=None, data=None) -> None:
        """Callback for clicking the logout button.

        Calls the logout function on the engine and displays the status.
        """
        dpg.configure_item("login_status_text", show=False)

        dpg.set_value("username_input", "")
        dpg.set_value("password_input", "")

        result = self.engine.logout()
        self._set_status_text_conditionally(
            "login_status_text", result, "Logged out", "Logout error"
        )
        dpg.set_value("remember_me_checkbox", False)

    def _set_downloads_dir(self, sender=None, data=None) -> None:
        """Callback for exiting the downloads directory selection file dialog.

        This sets the text input for the download directory to the selected
        directory from the file dialog.
        """
        dpg.set_value("downloads_dir_input", data["file_path_name"])

    def _show_downloads_dir_dialog(self, sender=None, data=None) -> None:
        """Callback for browsing for download directory in settings.

        Creates a new dialog allowing the user to select a directory.
        """
        if dpg.does_item_exist("downloads_dir_dialog"):
            dpg.delete_item("downloads_dir_dialog")

        dpg.add_file_dialog(
            tag="downloads_dir_dialog",
            directory_selector=True,
            default_path=dpg.get_value("downloads_dir_input"),
            callback=self._set_downloads_dir,
        )

    def _save_settings(self, sender=None, data=None) -> None:
        """Callback for clicking the save settings button.

        Writes the configuration to file.
        """
        dpg.configure_item("settings_status_text", show=False)

        username = ""
        password = ""
        if dpg.get_value("remember_me_checkbox"):
            username = dpg.get_value("username_input")
            password = dpg.get_value("password_input")
        downloads_dir = Path(dpg.get_value("downloads_dir_input"))
        filetype = dpg.get_value("filetype_combo")
        should_use_threading = dpg.get_value("use_threading_checkbox")
        concurrency_limit = dpg.get_value("concurrency_limit_input")
        should_rate_limit = dpg.get_value("rate_limit_checkbox")
        result = self.engine.update_settings(
            username=username,
            password=password,
            downloads_dir=downloads_dir,
            filetype=filetype,
            should_use_threading=should_use_threading,
            concurrency_limit=concurrency_limit,
            should_rate_limit=should_rate_limit,
        )

        self._set_status_text_conditionally(
            "settings_status_text",
            result,
            "Saved! Restart for engine changes.",
            "Save error",
        )

    def _reset_settings(self, sender=None, data=None) -> None:
        """Callback for clicking the reset settings button.

        Re-reads the existing configuration file.
        """
        dpg.configure_item("settings_status_text", show=False)
        result = self.engine.get_settings()

        if result == 0:
            dpg.set_value("username_input", self.engine.config.username)
            dpg.set_value("password_input", self.engine.config.password)
            dpg.set_value(
                "remember_me_checkbox",
                any((self.engine.config.username, self.engine.config.password)),
            )
            dpg.set_value("downloads_dir_input", str(self.engine.config.downloads_dir))
            dpg.set_value("filetype_combo", self.engine.config.filetype)
            dpg.set_value("rate_limit_checkbox", self.engine.config.should_rate_limit)
            dpg.set_value(
                "use_threading_checkbox", self.engine.config.should_use_threading
            )
            dpg.set_value(
                "concurrency_limit_input", self.engine.config.concurrency_limit
            )

        self._set_status_text_conditionally(
            "settings_status_text",
            result,
            "Loaded saved settings!",
            "Error loading settings",
        )

    def _open_file(self, sender=None, data=None, user_data=None):
        """Callback for clicking the open button on a work.

        Tries to open the destination of the downloaded file with the system
        default applications.
        """
        utils.open_file(user_data["path"])

    def _remove_work_item(self, sender=None, data=None, user_data=None) -> None:
        """Callback for clicking the X button on a work.

        Remove this work from the UI and also tell the engine to remove it.
        """
        work_id = user_data["work_id"]
        self.engine.remove(work_id)
        if work_id in self._work_ids:
            self._work_ids.remove(work_id)
        if work_id in self._downloaded:
            self._downloaded.remove(work_id)

        window_tag = f"{work_id}_window"
        if dpg.does_item_exist(window_tag):
            dpg.delete_item(window_tag)

    def _remove_all(self, sender=None, data=None) -> None:
        """Callback for clicking the X button on a work.

        Remove all works currently staged.
        """
        while self._work_ids:
            work_id = self._work_ids.pop()
            if work_id in self._downloaded:
                self._downloaded.remove(work_id)
            self.engine.remove(work_id)
            window_tag = f"{work_id}_window"
            if dpg.does_item_exist(window_tag):
                dpg.delete_item(window_tag)

    def _toggle_loading_on_work(self, work_id: int, show_loading=False):
        """Toggle the visibility of the loading indicator on a work.

        When the loading indicator is visible, the remove/open buttons are
        hidden.
        """
        dpg.configure_item(f"{work_id}_loading", show=show_loading)
        dpg.configure_item(f"{work_id}_remove_button", show=not show_loading)

    def _toggle_all_buttons_enabled(self, enabled=False) -> None:
        """Toggle whether the open/close buttons are enabled an a work.

        Disable the buttons while a request for the work is ongoing.
        When the buttons are disabled, clicking them will have no effect.
        This is to prevent corruption of internal state since there are
        multiple threads trying to modify these containers at the same time.
        These buttons will be reenabled in the callbacks when the request
        completes.
        TODO: make this not necessary.
        """
        dpg.configure_item("download_button", enabled=enabled)
        dpg.configure_item("remove_all_button", enabled=enabled)
        dpg.configure_item("add_works_button", enabled=enabled)
        dpg.configure_item("add_bookmarks_button", enabled=enabled)

        for work_id in self._work_ids:
            if dpg.does_item_exist(f"{work_id}_window"):
                dpg.configure_item(f"{work_id}_remove_button", enabled=enabled)
                dpg.configure_item(f"{work_id}_open_button", enabled=enabled)

    def _update_work_item_after_load(
        self,
        work_id: int,
        data: Dict[str, Any] = {},
        error_message: Optional[str] = None,
    ) -> None:
        """Callback to be called by the engine.

        When the engine completes loading of a work (which may be in another 
        thread), this function will be called to update the placeholder item
        with the real work metadata.

        If an error occurs, an error message will be printed.
        """
        if error_message:
            self._toggle_loading_on_work(
                work_id, show_loading=data.get("show_loading", False)
            )
            dpg.configure_item(f"{work_id}_title", color=(255, 0, 0), show=True)
            dpg.set_value(f"{work_id}_title", error_message)
            dpg.configure_item(f"{work_id}_content_group", show=True)
            dpg.configure_item(f"{work_id}_metadata_group", show=False)
            return

        # TODO: update fonts to render properly
        work = data["work"]
        self._toggle_loading_on_work(work_id, show_loading=False)
        dpg.configure_item(f"{work_id}_content_group", show=True)
        dpg.configure_item(f"{work_id}_metadata_group", show=True)
        dpg.configure_item(f"{work_id}_title", color=(255, 255, 255), show=True)
        dpg.set_value(f"{work_id}_title", f"{work.title}")
        authors = ", ".join(author.strip() for author in work.metadata["authors"])
        dpg.set_value(f"{work_id}_author", f"Author(s): {authors}")
        dpg.set_value(
            f"{work_id}_chapters",
            f"Chapters: {work.metadata['nchapters']}/{work.metadata['expected_chapters'] or '?'}",
        )
        dpg.set_value(f"{work_id}_words", f"Words: {work.metadata['words']}")
        dpg.set_value(
            f"{work_id}_date_edited", f"Edited: {work.metadata['date_edited'].strip()}"
        )

    def _update_work_item_after_download(
        self,
        work_id: int,
        data: Dict[str, Any] = {},
        error_message: Optional[str] = None,
    ) -> None:
        """Callback to be called by the engine.

        When the engine completes downloading of a work (which may be in another 
        thread), this function will be called to show the open button and
        download status text.

        If an error occurs, the error message will be printed.

        The works must also be loaded before being downloaded, so this function
        will also attempt to update the work elements with metadata before
        downloading.
        """
        if error_message:
            self._toggle_loading_on_work(
                work_id, show_loading=data.get("show_loading", False)
            )
            dpg.configure_item(f"{work_id}_open_button", show=False)
            dpg.configure_item(f"{work_id}_download_status_group", show=True)
            dpg.configure_item(f"{work_id}_download_status_text", color=(255, 0, 0))
            dpg.set_value(f"{work_id}_download_status_text", error_message)
            return

        self._toggle_loading_on_work(work_id, show_loading=False)
        dpg.configure_item(f"{work_id}_open_button", show=True)
        dpg.configure_item(f"{work_id}_download_status_group", show=True)
        dpg.configure_item(f"{work_id}_download_status_text", color=(0, 255, 0))
        dpg.set_value(f"{work_id}_download_status_text", "Downloaded")
        dpg.set_item_user_data(f"{work_id}_open_button", {"path": data["path"]})
        self._downloaded.add(work_id)

    def _show_urls_dialog(self, sender=None, data=None) -> None:
        """Callback for when certain 'add works' buttons are clicked.

        Displays a small popup window with a multiline textbox where users can
        enter URLs.
        """
        add_type = ""
        if sender == "add_works_button":
            add_type = "works"
        elif sender == "add_series_button":
            add_type = "series"
        dpg.configure_item("urls_dialog", label=f"Add {add_type.title()}", show=True)
        dpg.set_item_user_data("submit_urls_button", {"add_type": add_type})
        dpg.set_value("urls_input", "")

    def _load_works(self, work_ids: Set[int]) -> None:
        """Common function for loading a bunch of work IDs.

        Will show the placeholder items, try to load the works and display
        status messages as necessary.
        """
        self._toggle_all_buttons_enabled(enabled=False)
        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=True)

        dpg.set_value("add_works_status_text", f"Loading {len(work_ids)} works...")

        previous_id_count = len(self._work_ids)
        self._work_ids.update(work_ids)
        for work_id in work_ids:
            self._show_placeholder_work_item(work_id)
        self.engine.load_works(work_ids, callback=self._update_work_item_after_load)

        id_delta = len(self._work_ids) - previous_id_count
        if id_delta:
            dpg.configure_item("add_works_status_text", color=(0, 255, 0), show=True)
            dpg.set_value("add_works_status_text", f"Loaded {id_delta} works")
            dpg.configure_item("download_status_text", show=False)
        else:
            dpg.configure_item("add_works_status_text", show=False)
        self._toggle_all_buttons_enabled(enabled=True)

    def _add_urls(self, sender=None, data=None, user_data=None) -> None:
        """Callback for when the OK button is clicked on the add works dialog.

        This will call the appropriate function to load works depending on
        what the caller was.
        """

        # TODO: add an error message if some works in list couldn't be loaded
        add_type = user_data["add_type"]
        dpg.configure_item("urls_dialog", show=False)
        urls = set(
            filter(
                None, [url.strip() for url in dpg.get_value("urls_input").split("\n")]
            )
        )

        work_ids = set()
        if add_type == "works":
            work_ids = self.engine.work_urls_to_work_ids(urls)
        elif add_type == "series":
            # TODO: enable adding series
            pass
        self._load_works(work_ids)

    def _add_bookmarks(self, sender=None, data=None) -> None:
        """Callback for when the add bookmarks button is clicked.

        Calls the engine to get all bookmarks and attempt to load them all.
        """
        if not self.engine.session.is_authed:
            dpg.configure_item("add_works_status_text", color=(255, 0, 0), show=True)
            dpg.set_value("add_works_status_text", "Not logged in!")
            return

        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=True)
        dpg.set_value("add_works_status_text", "Getting bookmarks...")
        bookmark_ids = self.engine.get_bookmark_ids()
        self._load_works(bookmark_ids)

    def _download_all(self, sender=None, data=None) -> None:
        """Callback for when the download all button is clicked.

        Calls the engine to attempt download for all IDs staged right now.
        """
        self._toggle_all_buttons_enabled(enabled=False)
        dpg.configure_item("download_status_text", color=(255, 255, 0), show=True)
        dpg.set_value(
            "download_status_text", f"Downloading {len(self._work_ids)} works..."
        )

        for work_id in self._work_ids:
            self._show_placeholder_work_item(work_id)
            dpg.configure_item(f"{work_id}_download_status_group", show=False)
        self.engine.load_works(
            self._work_ids, callback=self._update_work_item_after_load
        )
        for work_id in self._work_ids:
            self._toggle_loading_on_work(work_id, show_loading=True)
            dpg.configure_item(f"{work_id}_download_status_group", show=False)
            dpg.configure_item(f"{work_id}_open_button", show=False)
        self.engine.download_works(
            self._work_ids, callback=self._update_work_item_after_download
        )

        dpg.configure_item("download_status_text", color=(0, 255, 0), show=True)
        dpg.set_value(
            "download_status_text", f"Finished downloading {len(self._work_ids)} works"
        )
        self._toggle_all_buttons_enabled(enabled=True)

    def _make_gui(self) -> None:
        """Create the layout for the entire application."""
        with dpg.window(label="ao3d", tag="primary_window"):
            with dpg.tab_bar(tag="tabs"):
                self._make_settings_tab()
                self._make_downloads_tab()

    def _make_settings_tab(self) -> None:
        """Create the layout for the settings tab."""
        with dpg.tab(label="Settings", tag="settings_tab"):
            with dpg.child_window(
                tag="settings_child_window", width=500, height=410,
            ):
                with dpg.group(tag="login_settings_group"):
                    dpg.add_text("AO3 Login", tag="login_settings_text")
                    with dpg.group(tag="username_group", horizontal=True):
                        dpg.add_text("Username:", tag="username_text")
                        dpg.add_input_text(
                            tag="username_input",
                            default_value=self.engine.config.username,
                        )
                    with dpg.group(tag="password_group", horizontal=True):
                        dpg.add_text("Password:", tag="password_text")
                        dpg.add_input_text(
                            tag="password_input",
                            password=True,
                            default_value=self.engine.config.password,
                        )
                    dpg.add_spacer(tag="login_button_spacer")
                    with dpg.group(tag="login_button_group", horizontal=True):
                        dpg.add_button(
                            label="Login",
                            tag="login_button",
                            small=True,
                            callback=self._login,
                        )
                        dpg.add_button(
                            label="Logout",
                            tag="logout_button",
                            small=True,
                            callback=self._logout,
                        )
                        dpg.add_text(
                            "", tag="login_status_text", show=False, indent=200
                        )
                        if self.engine.config.username or self.engine.config.password:
                            self._set_status_text_conditionally(
                                "login_status_text",
                                # Since this function compares if result == 0
                                not self.engine.session.is_authed,
                                f"Logged in as: {self.engine.session.username}",
                                "Not logged in",
                            )

                    dpg.add_checkbox(
                        label="Remember me?",
                        tag="remember_me_checkbox",
                        default_value=any(
                            (self.engine.config.username, self.engine.config.password)
                        ),
                    )
                dpg.add_spacer(tag="login_group_spacer", height=20)

                with dpg.group(tag="download_settings_group"):
                    dpg.add_text("Downloads", tag="download_settings_text")
                    with dpg.group(tag="downloads_dir_group", horizontal=True):
                        dpg.add_text("Directory:", tag="downloads_dir_text")
                        dpg.add_input_text(
                            tag="downloads_dir_input",
                            default_value=self.engine.config.downloads_dir.resolve(),
                        )
                        dpg.add_button(
                            label="Browse",
                            tag="downloads_dir_dialog_button",
                            callback=self._show_downloads_dir_dialog,
                            small=True,
                        )
                    with dpg.group(tag="filetype_group", horizontal=True):
                        dpg.add_text("Filetype:", tag="filetype_text")
                        dpg.add_combo(
                            items=list(constants.VALID_FILETYPES),
                            tag="filetype_combo",
                            default_value=constants.DEFAULT_DOWNLOADS_FILETYPE,
                            width=50,
                        )
                dpg.add_spacer(tag="download_settings_group_spacer", height=20)

                with dpg.group(tag="engine_settings_group"):
                    dpg.add_text("Engine", tag="engine_settings_text")
                    with dpg.group(tag="use_threading_group", horizontal=True):
                        dpg.add_text("Use threading?", tag="use_threading_text")
                        dpg.add_checkbox(
                            tag="use_threading_checkbox",
                            default_value=self.engine.config.should_use_threading,
                        )
                    with dpg.group(tag="concurrency_limit_group", horizontal=True):
                        dpg.add_text("Concurrency limit:", tag="concurrency_limit_text")
                        dpg.add_input_int(
                            tag="concurrency_limit_input",
                            default_value=self.engine.config.concurrency_limit,
                            min_value=1,
                            max_value=20,
                            min_clamped=True,
                            max_clamped=True,
                        )
                    with dpg.group(tag="rate_limit_group", horizontal=True):
                        dpg.add_text("Use rate limiting?", tag="rate_limit_text")
                        dpg.add_checkbox(
                            tag="rate_limit_checkbox",
                            default_value=self.engine.config.should_rate_limit,
                        )
                dpg.add_spacer(tag="engine_settings_group_spacer", height=20)
                with dpg.group(tag="save_settings_group", horizontal=True):
                    dpg.add_button(
                        label="Save settings",
                        tag="save_settings_button",
                        callback=self._save_settings,
                    )
                    dpg.add_button(
                        label="Reset",
                        tag="reset_settings_button",
                        callback=self._reset_settings,
                    )
                    dpg.add_text("", tag="settings_status_text", indent=200, show=False)

    def _make_downloads_tab(self) -> None:
        """Create the layout for the downloads tab."""
        with dpg.tab(label="Downloads", tag="downloads_tab"):
            dpg.add_spacer(tag="add_works_top_spacer", height=20)
            with dpg.group(tag="add_works_buttons", horizontal=True):
                dpg.add_text("Add works to download: ", tag="add_works_text")
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Add works",
                    tag="add_works_button",
                    callback=self._show_urls_dialog,
                )
                # TODO: enable adding series
                # dpg.add_button(
                #     label="Add series",
                #     tag="add_series_button",
                #     callback=self._show_urls_dialog,
                # )
                dpg.add_button(
                    label="Add bookmarks",
                    tag="add_bookmarks_button",
                    callback=self._add_bookmarks,
                )
                dpg.add_spacer(width=50)
                dpg.add_text(tag="add_works_status_text", show=False)
            dpg.add_spacer(tag="works_group_spacer")
            dpg.add_child_window(tag="works_window", autosize_x=True, height=620)
            dpg.add_spacer(height=20)
            with dpg.child_window(
                tag="downloads_footer", border=False, autosize_x=True, autosize_y=True
            ):
                with dpg.group(tag="downloads_footer_group", horizontal=True):
                    dpg.add_button(
                        label="Download all",
                        tag="download_button",
                        height=50,
                        width=100,
                        callback=self._download_all,
                    )
                    dpg.add_button(
                        label="Remove all",
                        tag="remove_all_button",
                        height=50,
                        width=100,
                        callback=self._remove_all,
                    )
                    dpg.add_spacer(width=40)
                    with dpg.group(tag="downloads_footer_text_group"):
                        dpg.add_spacer(height=12)
                        dpg.add_text(tag="download_status_text", show=False)
            with dpg.window(
                label="Add URLs",
                tag="urls_dialog",
                width=600,
                height=300,
                pos=(
                    (dpg.get_viewport_width() - 600) // 2,
                    (dpg.get_viewport_height() - 300) // 2,
                ),
                show=False,
            ):
                dpg.add_text("Enter URLs on a new line each:", tag="urls_dialog_text")
                dpg.add_input_text(
                    tag="urls_input", multiline=True, width=580, height=200
                )
                dpg.add_button(
                    label="OK",
                    tag="submit_urls_button",
                    small=True,
                    callback=self._add_urls,
                )

    def _show_placeholder_work_item(self, work_id: int) -> None:
        """Shows the default placeholder item for a work.

        This will create a UI element for the work if it does not already exist
        or simply show/hide the sub-elements and disable the buttons if the
        element already exists.
        """
        window_tag = f"{work_id}_window"
        if dpg.does_item_exist(window_tag):
            dpg.configure_item(f"{work_id}_loading", show=True)
            dpg.configure_item(f"{work_id}_content_group", show=False)
            return

        with dpg.child_window(
            tag=window_tag, parent="works_window", autosize_x=True, height=60
        ):
            with dpg.group(tag=f"{work_id}_group", horizontal=True):
                dpg.add_button(
                    label="X",
                    tag=f"{work_id}_remove_button",
                    width=40,
                    height=40,
                    callback=self._remove_work_item,
                    user_data={"work_id": work_id},
                    show=False,
                    enabled=False,
                )
                dpg.add_loading_indicator(tag=f"{work_id}_loading", show=True)
                dpg.add_button(
                    label="Open",
                    tag=f"{work_id}_open_button",
                    width=40,
                    height=40,
                    callback=self._open_file,
                    show=False,
                    enabled=False,
                )
                dpg.add_spacer()
                with dpg.group(
                    tag=f"{work_id}_content_group", horizontal=True, show=False
                ):
                    with dpg.child_window(
                        tag=f"{work_id}_layout_left",
                        border=False,
                        width=dpg.get_viewport_width() - 120,
                        autosize_y=True,
                    ):
                        with dpg.group(tag=f"{work_id}_title_group", horizontal=True):
                            dpg.add_text(f"{work_id}", tag=f"{work_id}_id")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_title")
                            with dpg.group(
                                tag=f"{work_id}_download_status_group",
                                horizontal=True,
                                show=False,
                            ):
                                dpg.add_spacer(width=30)
                                dpg.add_text(tag=f"{work_id}_download_status_text")
                        with dpg.group(
                            tag=f"{work_id}_metadata_group", horizontal=True
                        ):
                            dpg.add_text(tag=f"{work_id}_author")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_chapters")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_words")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_date_edited")
                            dpg.add_spacer(width=60)

    def run(self) -> None:
        """Starts the GUI."""
        dpg.create_context()
        dpg.create_viewport(title="ao3d")
        dpg.setup_dearpygui()
        self._make_gui()
        dpg.set_primary_window("primary_window", True)
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()
