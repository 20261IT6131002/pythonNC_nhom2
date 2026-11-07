"""Main-thread confirmations for unsaved in-memory content."""

from tkinter import Misc, colorchooser, filedialog, messagebox, simpledialog

from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState


def confirm_discard(root: Misc, state: EditorState) -> bool:
    if not state.unsaved:
        return True
    message = "Nội dung chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
    if state.phase == EditorPhase.SAVING:
        message = (
            "Thao tác lưu đang xử lý và có thể vẫn hoàn tất. "
            "Nội dung chỉnh sửa chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
        )
    return messagebox.askyesno("Nội dung chưa lưu", message, parent=root)


def confirm_trash(root: Misc) -> bool:
    return messagebox.askyesno(
        "Chuyển vào thùng rác",
        "Chuyển ghi chú này vào thùng rác? Bạn có thể khôi phục sau.",
        parent=root,
    )


def confirm_purge(root: Misc) -> bool:
    return messagebox.askyesno(
        "Xóa vĩnh viễn",
        "Xóa vĩnh viễn ghi chú này? Thao tác này không thể hoàn tác.",
        parent=root,
        icon="warning",
    )


def ask_category_name(parent: Misc, title: str, initial: str = "") -> str | None:
    return simpledialog.askstring(title, "Tên danh mục:", initialvalue=initial, parent=parent)


def ask_category_color(parent: Misc, initial: str) -> str | None:
    _, chosen = colorchooser.askcolor(color=initial, title="Chọn màu danh mục", parent=parent)
    return chosen.upper() if chosen else None


def confirm_delete_category(parent: Misc, name: str) -> bool:
    return messagebox.askyesno(
        "Xóa danh mục",
        f"Xóa danh mục “{name}”? Danh mục đang có ghi chú sẽ không thể xóa.",
        parent=parent,
        icon="warning",
    )


def ask_image_file(parent: Misc) -> str | None:
    # The filter is a convenience only; content is verified by decoding, not by extension.
    path = filedialog.askopenfilename(
        parent=parent,
        title="Chọn ảnh đính kèm",
        filetypes=(("Ảnh", "*.png *.jpg *.jpeg *.gif *.webp"), ("Tất cả tệp", "*.*")),
    )
    return path or None


def confirm_remove_image(parent: Misc) -> bool:
    return messagebox.askyesno(
        "Gỡ ảnh", "Gỡ ảnh đính kèm khỏi ghi chú này?", parent=parent, icon="warning"
    )


def ask_passphrase(parent: Misc, title: str, *, confirm: bool = False) -> str | None:
    prompt = (
        "Nhập cụm mật khẩu (ít nhất 12 ký tự). Không thể khôi phục nếu quên."
        if confirm
        else "Nhập cụm mật khẩu của ghi chú."
    )
    value = simpledialog.askstring(title, prompt, parent=parent, show="*")
    if value is None or not confirm:
        return value
    repeated = simpledialog.askstring(title, "Nhập lại cụm mật khẩu.", parent=parent, show="*")
    if repeated is None:
        return None
    if value != repeated:
        messagebox.showwarning(title, "Hai cụm mật khẩu không khớp.", parent=parent)
        return None
    return value


def confirm_remove_lock(parent: Misc) -> bool:
    return messagebox.askyesno(
        "Bỏ khóa vĩnh viễn",
        "Tiêu đề và nội dung sẽ được lưu dưới dạng văn bản thường. Tiếp tục?",
        parent=parent,
        icon="warning",
    )


def confirm_idle_discard(parent: Misc) -> bool:
    return messagebox.askyesno(
        "Phiên mở khóa đã hết hạn",
        "Chưa xác nhận lưu bản nháp mã hóa. Bỏ các thay đổi chưa lưu để khóa lại ngay?",
        parent=parent,
        icon="warning",
    )
