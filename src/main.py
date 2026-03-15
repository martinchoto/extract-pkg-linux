import customtkinter as ctk
import os
import subprocess
import threading
import json
import sys
import time
from tkinter import messagebox, PhotoImage

# --- APPIMAGE PATH HANDLING ---
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pkg_installer_config.json")
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_PATH = os.path.join(BUNDLE_DIR, "config.json")

def get_bundle_path(rel_path):
    return os.path.join(BUNDLE_DIR, rel_path)

def open_native_picker(title, folder=False):
    
    cmd = ["pkexec"] if os.geteuid() == 0 else [] # Handle root if needed
    if folder:
        
        cmd = ["zenity", "--file-selection", "--directory", f"--title={title}"]
    else:
        
        cmd = ["zenity", "--file-selection", f"--title={title}", "--file-filter=*.pkg"]
    
    try:
        path = subprocess.check_output(cmd).decode("utf-8").strip()
        return path
    except:
        return None

class PKGInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PKG Installer Tool")
        self.geometry("850x780")
        self.configure(fg_color="#0a0f1e")

        self.appimage = get_bundle_path("pkg_extractor.AppImage")
        self.logo_path = get_bundle_path("logo.png")
        
        self.pkg_path = ctk.StringVar()
        self.game_path = ctk.StringVar(value="") # Empty by default
        self.addon_path = ctk.StringVar(value=os.path.expanduser("~/.local/share/shadPS4/user/addcont"))

        self.load_config()
        self.setup_ui()
        self.set_linux_icon()
        self.active_process = None

    def browse_pkg(self):
        # We use standard tkinter filedialog as a fallback because it's built-in
        from tkinter import filedialog
        p = filedialog.askopenfilename(title="Select PKG", filetypes=[("PKG files", "*.pkg")])
        if p: self.pkg_path.set(p)

    def browse_folder(self, var):
        from tkinter import filedialog
        p = filedialog.askdirectory(title="Select Destination Folder")
        if p: 
            var.set(p)
            self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    if "game_path" in data: self.game_path.set(data["game_path"])
                    if "addon_path" in data: self.addon_path.set(data["addon_path"])
            except: pass

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({"game_path": self.game_path.get(), "addon_path": self.addon_path.get()}, f, indent=4)
        except: pass

    def set_linux_icon(self):
        if os.path.exists(self.logo_path):
            try:
                img = PhotoImage(file=self.logo_path)
                self.iconphoto(False, img)
            except: pass

    def setup_ui(self):
        self.lbl_title = ctk.CTkLabel(self, text="PKG Installer Tool", font=ctk.CTkFont(family="Impact", size=44), text_color="#4db8ff")
        self.lbl_title.pack(pady=(30, 10))
        
        self.create_row("SELECT PKG FILE", self.pkg_path, self.browse_pkg)
        self.create_row("GAME DATA LOCATION", self.game_path, lambda: self.browse_folder(self.game_path))
        self.create_row("DLC / ADDON LOCATION", self.addon_path, lambda: self.browse_folder(self.addon_path))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=60, pady=25, fill="x")

        self.install_btn = ctk.CTkButton(btn_frame, text="START INSTALL", height=55, fg_color="#1f538d", command=self.start_thread)
        self.install_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_btn = ctk.CTkButton(btn_frame, text="STOP", width=120, height=55, fg_color="#440000", command=self.kill_process, state="disabled")
        self.stop_btn.pack(side="right")

        self.log = ctk.CTkTextbox(self, height=280, fg_color="#010409", text_color="#00ffcc")
        self.log.pack(padx=20, pady=10, fill="both", expand=True)

    def create_row(self, label, var, cmd):
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8892b0").pack(anchor="w", padx=60, pady=(15, 0))
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=60, pady=5)
        ctk.CTkEntry(f, textvariable=var, height=38, fg_color="#1b263b").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(f, text="BROWSE", width=90, command=cmd).pack(side="right")

    def kill_process(self):
        if self.active_process: self.active_process.terminate()

    def start_thread(self):
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        pkg, target_game = self.pkg_path.get(), self.game_path.get()
        if not pkg or not target_game:
            messagebox.showwarning("Warning", "Please select both PKG and Game Path.")
            return

        self.install_btn.configure(state="disabled", text="INSTALLING...")
        self.stop_btn.configure(state="normal")
        self.log.delete("1.0", "end")

        try:
            # Clear LD_LIBRARY_PATH so the sub-appimage doesn't crash
            env = os.environ.copy()
            env.pop('LD_LIBRARY_PATH', None)

            check = subprocess.run([self.appimage, pkg, '--check-type'], capture_output=True, env=env)
            final_target = self.addon_path.get() if check.returncode == 103 else target_game
            
            self.active_process = subprocess.Popen(
                ['nice', '-n', '10', self.appimage, pkg, final_target],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env
            )

            for line in iter(self.active_process.stdout.readline, ''):
                self.log.insert("end", line)
                self.log.see("end")

            if self.active_process.wait() == 0:
                messagebox.showinfo("Done", "Successfully installed!")
        except Exception as e:
            self.log.insert("end", f"\n[CRITICAL ERROR] {str(e)}\n")
        finally:
            self.install_btn.configure(state="normal", text="START INSTALL")
            self.stop_btn.configure(state="disabled")

if __name__ == "__main__":
    app = PKGInstaller()
    app.mainloop()