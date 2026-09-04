import base64
from datetime import datetime
import json
import os
import plistlib
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.request

GOLD_PRODUCT = "locket_1600_1y"
EXPIRES_ISO = "2099-12-31T23:59:59Z"


def now_iso_z():
  return (
      datetime.utcnow()
      .isoformat()
      .replace("+00:00", "Z")
      .replace(".000000", "")
      + "Z"
  )


def extract_uid(etags_obj):
  """Trích xuất UID từ etags dictionary."""
  for k in etags_obj.keys():
    m = re.search(r"/v1/subscribers/([^/?#]+)", k)
    if m:
      return {"uid": m.group(1), "key": k}
  return None


def validate_etags_file(path):
  """Kiểm tra tên tệp và định dạng của Etags Plist."""
  file_name = os.path.basename(path)

  # Kiểm tra chính xác tên tệp Etags
  if file_name != "com.locket.Locket.revenuecat.etags.plist":
    return (
        False,
        f"Tên tệp không đúng!\nTệp được chọn phải là:"
        " com.locket.Locket.revenuecat.etags.plist\n(Tệp bạn chọn: "
        f"{file_name})",
    )

  try:
    with open(path, "rb") as f:
      etags = plistlib.loads(f.read())
    found = extract_uid(etags)
    if not found:
      return (
          False,
          "Tệp plist hợp lệ nhưng không tìm thấy dữ liệu UID/Subscriber Locket!",
      )
    return True, f"UID: {found['uid']}"
  except Exception as e:
    return False, f"Tệp Etags không đúng định dạng Plist:\n{str(e)}"


def validate_app_plist_file(path):
  """Kiểm tra tên tệp và định dạng của App Plist."""
  file_name = os.path.basename(path)

  # Kiểm tra chính xác tên tệp App Plist
  if file_name != "com.locket.Locket.plist":
    return (
        False,
        f"Tên tệp không đúng!\nTệp được chọn phải là: com.locket.Locket.plist\n(Tệp bạn"
        f" chọn: {file_name})",
    )

  try:
    with open(path, "rb") as f:
      app_data = plistlib.loads(f.read())
    if not isinstance(app_data, dict):
      return False, "Dữ liệu tệp App Plist không hợp lệ (Không phải Dictionary)."
    return True, "Tệp App Plist hợp lệ"
  except Exception as e:
    return False, f"Tệp App Plist không đúng định dạng Plist:\n{str(e)}"


def forge_subscriber(uid, sub_obj):
  now = now_iso_z()
  now_ms = int(datetime.utcnow().timestamp() * 1000)
  s = sub_obj.setdefault("subscriber", {})
  s["entitlements"] = {
      "Gold": {
          "expires_date": EXPIRES_ISO,
          "grace_period_expires_date": None,
          "product_identifier": GOLD_PRODUCT,
          "purchase_date": now,
      }
  }
  s["subscriptions"] = {
      GOLD_PRODUCT: {
          "billing_issues_detected_at": None,
          "expires_date": EXPIRES_ISO,
          "grace_period_expires_date": None,
          "is_sandbox": False,
          "original_purchase_date": now,
          "ownership_type": "PURCHASED",
          "period_type": "normal",
          "purchase_date": now,
          "refunded_at": None,
          "store": "app_store",
          "unsubscribe_detected_at": None,
      }
  }
  sub_obj["request_date"] = now
  sub_obj["request_date_ms"] = now_ms
  return sub_obj


def process_files(etags_path, app_plist_path, output_dir):
  with open(etags_path, "rb") as f:
    etags_bytes = f.read()

  etags = plistlib.loads(etags_bytes)
  found = extract_uid(etags)
  if not found:
    raise ValueError("Không tìm thấy UID người dùng hợp lệ trong tệp etags.")

  uid, key = found["uid"], found["key"]
  entry = etags[key]

  if isinstance(entry, bytes):
    entry = json.loads(entry.decode("utf-8"))
  elif isinstance(entry, str):
    entry = json.loads(entry)

  sub_data = base64.b64decode(entry["data"])
  sub_obj = json.loads(sub_data.decode("utf-8"))

  forge_subscriber(uid, sub_obj)

  entry["data"] = base64.b64encode(
      json.dumps(sub_obj).encode("utf-8")
  ).decode("utf-8")
  etags[key] = json.dumps(entry).encode("utf-8")

  etags_out = plistlib.dumps(etags, fmt=plistlib.FMT_BINARY)

  os.makedirs(output_dir, exist_ok=True)

  out_etags_path = os.path.join(
      output_dir, "com.locket.Locket.revenuecat.etags.plist"
  )
  with open(out_etags_path, "wb") as f:
    f.write(etags_out)

  if app_plist_path:
    with open(app_plist_path, "rb") as f:
      app = plistlib.loads(f.read())

    app["/subscription_local_trial_started_at"] = datetime.utcnow()
    app["/subscription_local_trial_ended_at"] = datetime(
        2099, 12, 31, 23, 59, 59
    )
    out_app_path = os.path.join(output_dir, "com.locket.Locket.plist")
    with open(out_app_path, "wb") as f:
      f.write(plistlib.dumps(app, fmt=plistlib.FMT_BINARY))

  return uid


class LocketPatcherApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Up Locket Gold by Lucas")
    self.root.geometry("540x370")
    self.root.resizable(False, False)

    self.etags_file = ""
    self.app_plist_file = ""
    self.output_dir = ""

    self.setup_background()
    self.create_widgets()

  def setup_background(self):
    bg_url = "https://github.com/Duc3435G/Custom-image/blob/main/a.png?raw=true"
    try:
      req = urllib.request.Request(
          bg_url, headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req) as response:
        image_data = response.read()

      self.bg_image = tk.PhotoImage(data=base64.b64encode(image_data))
      self.canvas = tk.Canvas(self.root, width=540, height=370, highlightthickness=0)
      self.canvas.pack(fill="both", expand=True)
      self.canvas.create_image(0, 0, image=self.bg_image, anchor="nw")
    except Exception as e:
      print(f"Không thể tải ảnh nền: {e}")
      self.canvas = tk.Canvas(self.root, width=540, height=370, bg="#f0f0f0")
      self.canvas.pack(fill="both", expand=True)

  def make_button_smooth(
      self,
      btn,
      callback,
      normal_bg,
      hover_bg,
      press_bg,
      canvas_window_id=None,
      base_x=0,
      base_y=0,
  ):
    """Hiệu ứng chuyển màu nút mượt mà (không tiếng kêu)."""

    def on_enter(e):
      btn.config(bg=hover_bg)

    def on_leave(e):
      btn.config(bg=normal_bg)

    def on_press(e):
      btn.config(bg=press_bg)
      if canvas_window_id:
        self.canvas.coords(canvas_window_id, base_x + 1, base_y + 1)
      else:
        btn.place_configure(
            x=btn.winfo_x() + 1, y=btn.winfo_y() + 1
        ) if hasattr(btn, "place_info") else None

    def on_release(e):
      btn.config(bg=hover_bg)
      if canvas_window_id:
        self.canvas.coords(canvas_window_id, base_x, base_y)
      else:
        btn.place_configure(
            x=btn.winfo_x() - 1, y=btn.winfo_y() - 1
        ) if hasattr(btn, "place_info") else None
      callback()

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.bind("<Button-1>", on_press)
    btn.bind("<ButtonRelease-1>", on_release)

  def create_widgets(self):
    # Tiêu đề
    self.canvas.create_text(
        270,
        25,
        text="Tool up Locket by Lucas",
        font=("Arial", 13, "bold"),
        fill="#111111",
    )

    frames_config = [
        ("Tệp Etags:", self.select_etags, "lbl_etags", 75),
        ("Tệp App Plist:", self.select_app_plist, "lbl_app", 125),
        ("Thư mục lưu:", self.select_output_dir, "lbl_out", 175),
    ]

    for label_title, btn_command, attr_name, y_pos in frames_config:
      # Shadow cho Khung chính
      self.canvas.create_rectangle(
          53, y_pos - 13, 493, y_pos + 19, fill="#1e1e1e", outline=""
      )

      f = tk.Frame(self.root, bg="#ffffff", bd=0)

      tk.Label(
          f,
          text=label_title,
          width=12,
          anchor="w",
          bg="#ffffff",
          font=("Arial", 9, "bold"),
      ).pack(side="left", padx=(10, 2))

      lbl = tk.Label(
          f,
          text=(
              "Bắt buộc chọn..."
              if "Tệp" in label_title
              else "Chưa chọn..."
          ),
          fg="#777777",
          width=30,
          anchor="w",
          bg="#ffffff",
          font=("Arial", 9),
      )
      lbl.pack(side="left", padx=2)
      setattr(self, attr_name, lbl)

      btn_box = tk.Frame(f, bg="#ffffff", width=68, height=26)
      btn_box.pack(side="right", padx=(2, 6), pady=3)
      btn_box.pack_propagate(False)

      tk.Frame(btn_box, bg="#a0a0a0").place(
          x=2, y=2, width=64, height=22
      )

      btn_select = tk.Button(
          btn_box,
          text="Chọn",
          width=8,
          relief="flat",
          bg="#eaeaea",
          activebackground="#dedede",
          cursor="hand2",
          bd=0,
          font=("Arial", 9, "bold"),
          fg="#333333",
      )
      btn_select.place(x=0, y=0, width=64, height=22)
      self.make_button_smooth(
          btn_select, btn_command, "#eaeaea", "#dedede", "#cccccc"
      )

      self.canvas.create_window(270, y_pos, window=f, width=440, height=32)

    # Shadow cho Nút Bắt đầu
    self.canvas.create_rectangle(
        143, 236, 403, 274, fill="#152e42", outline=""
    )

    btn_run = tk.Button(
        self.root,
        text="BẮT ĐẦU VÁ VÀ XUẤT FILE",
        bg="#007bff",
        fg="white",
        font=("Arial", 10, "bold"),
        bd=0,
        relief="flat",
        activebackground="#0056b3",
        activeforeground="white",
        cursor="hand2",
    )
    run_win_id = self.canvas.create_window(
        270, 252, window=btn_run, width=260, height=36
    )

    self.make_button_smooth(
        btn_run,
        self.run_patch,
        normal_bg="#007bff",
        hover_bg="#0069d9",
        press_bg="#0052a3",
        canvas_window_id=run_win_id,
        base_x=270,
        base_y=252,
    )

    # Trạng thái
    self.status_text_id = self.canvas.create_text(
        270,
        305,
        text="Trạng thái: Sẵn sàng",
        font=("Arial", 10, "italic bold"),
        fill="#002266",
    )

    # Version
    self.canvas.create_text(
        270,
        330,
        text="Version 3.9",
        font=("Arial", 9, "bold"),
        fill="#555555",
    )

  def select_etags(self):
    path = filedialog.askopenfilename(
        title="Chọn tệp com.locket.Locket.revenuecat.etags.plist",
        filetypes=[("Plist Files", "*.plist"), ("All Files", "*.*")],
    )
    if path:
      is_valid, msg = validate_etags_file(path)
      if is_valid:
        self.etags_file = path
        self.lbl_etags.config(text=os.path.basename(path), fg="#008000")
        self.canvas.itemconfig(
            self.status_text_id,
            text=f"Kiểm tra Etags: {msg}",
            fill="#008000",
        )
      else:
        messagebox.showerror("Tệp Etags Không Hợp Lệ", msg)
        self.etags_file = ""
        self.lbl_etags.config(text="Tệp sai tên/lỗi, chọn lại...", fg="#cc0000")

  def select_app_plist(self):
    path = filedialog.askopenfilename(
        title="Chọn tệp com.locket.Locket.plist gốc",
        filetypes=[("Plist Files", "*.plist"), ("All Files", "*.*")],
    )
    if path:
      is_valid, msg = validate_app_plist_file(path)
      if is_valid:
        self.app_plist_file = path
        self.lbl_app.config(text=os.path.basename(path), fg="#008000")
        self.canvas.itemconfig(
            self.status_text_id,
            text="Kiểm tra App Plist: Hợp lệ",
            fill="#008000",
        )
      else:
        messagebox.showerror("Tệp App Plist Không Hợp Lệ", msg)
        self.app_plist_file = ""
        self.lbl_app.config(text="Tệp sai tên/lỗi, chọn lại...", fg="#cc0000")

  def select_output_dir(self):
    path = filedialog.askdirectory(title="Chọn thư mục lưu file đầu ra")
    if path:
      self.output_dir = path
      self.lbl_out.config(text=path, fg="#111111")

  def run_patch(self):
    if not self.etags_file:
      messagebox.showerror(
          "Lỗi",
          "Vui lòng chọn tệp Etags plist đúng tên"
          " `com.locket.Locket.revenuecat.etags.plist`!",
      )
      return
    if not self.app_plist_file:
      messagebox.showerror(
          "Lỗi",
          "Vui lòng chọn tệp App Plist đúng tên `com.locket.Locket.plist`!",
      )
      return
    if not self.output_dir:
      messagebox.showerror("Lỗi", "Vui lòng chọn thư mục để xuất kết quả!")
      return

    try:
      uid = process_files(
          self.etags_file, self.app_plist_file, self.output_dir
      )
      self.canvas.itemconfig(
          self.status_text_id,
          text=f"Thành công! UID: {uid[:8]}...",
          fill="#008000",
      )
      messagebox.showinfo(
          "Hoàn tất",
          f"Đã tạo thành công 2 file plist Locket trong thư mục:\n{self.output_dir}",
      )
    except Exception as e:
      self.canvas.itemconfig(
          self.status_text_id, text="Trạng thái: Lỗi xử lý", fill="#cc0000"
      )
      messagebox.showerror("Lỗi", f"Chi tiết lỗi:\n{str(e)}")


if __name__ == "__main__":
  root = tk.Tk()
  app = LocketPatcherApp(root)
  root.mainloop()
