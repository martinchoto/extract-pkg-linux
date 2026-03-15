import customtkinter as ctk
import os
import subprocess
import threading
import sys
import time
from tkinter import messagebox, PhotoImage, filedialog

# --- SCHEMATICS & PATH HANDLING ---
if getattr(sys, 'frozen', False):
    # Path inside the AppImage
    BUNDLE_DIR = sys._MEIPASS
else:
    # Path during development (assumes script is in /src)
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_bundle_path(rel_path):
    """Helper to locate files within the project structure"""
    return os.path.join(BUNDLE_DIR, rel_path)

class PKGInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PKG Installer Tool")
        self.geometry("850x780")
        self.configure(fg_color="#0a0f1e")

        # Hardcoded paths to match your build structure
        self.appimage_bin = get_bundle_path("bin/pkg_extractor.AppImage")
        self.logo_path = get_bundle_path("src/logo.png")
        
        # Variables (Game path starts empty as requested)
        self.pkg_path = ctk.StringVar()
        self.game_path = ctk.StringVar(value="") 
        self.addon_path = ctk.StringVar(value=os.path.expanduser("~/.local/share/shadPS4/user/addcont"))

        self.setup_ui()
        self.set_linux_icon()
        self.active_process = None

    def set_linux_icon(self):
        if os.path.exists(self.logo_path):
            try:
                img = PhotoImage(file=self.logo_path)
                self.iconphoto(False, img)
            except:
                pass

    def setup_ui(self):
        # Header
        self.lbl_title = ctk.CTkLabel(
            self, text="PKG Installer Tool", 
            font=ctk.CTkFont(family="Impact", size=44), 
            text_color="#4db8ff"
        )
        self.lbl_title.pack(pady=(30, 10))
        
        # Input Rows
        self.create_row("SELECT PKG FILE", self.pkg_path, self.browse_pkg)
        self.create_row("GAME DATA LOCATION", self.game_path, lambda: self.browse_folder(self.game_path))
        self.create_row("DLC / ADDON LOCATION", self.addon_path, lambda: self.browse_folder(self.addon_path))

        # Action Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=60, pady=25, fill="x")

        self.install_btn = ctk.CTkButton(
            btn_frame, text="START INSTALL", font=ctk.CTkFont(size=16, weight="bold"),
            height=55, fg_color="#1f538d", hover_color="#28a745", 
            command=self.start_thread
        )
        self.install_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="STOP", font=ctk.CTkFont(size=16, weight="bold"),
            width=120, height=55, fg_color="#440000", hover_color="#ff4444", 
            command=self.kill_process, state="disabled"
        )
        self.stop_btn.pack(side="right")

        # Output Console
        self.log = ctk.CTkTextbox(
            self, height=280, fg_color="#010409", 
            text_color="#00ffcc", font=("Monospace", 11)
        )
        self.log.pack(padx=20, pady=10, fill="both", expand=True)

    def create_row(self, label, var, cmd):
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8892b0").pack(anchor="w", padx=60, pady=(15, 0))
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=60, pady=5)
        ctk.CTkEntry(f, textvariable=var, height=38, fg_color="#1b263b", border_color="#333").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(f, text="BROWSE", width=90, command=cmd).pack(side="right")

    def browse_pkg(self):
        p = filedialog.askopenfilename(title="Select PKG", filetypes=[("PKG files", "*.pkg")])
        if p: self.pkg_path.set(p)

    def browse_folder(self, var):
        p = filedialog.askdirectory(title="Select Folder")
        if p: var.set(p)

    def kill_process(self):
        if self.active_process:
            self.active_process.terminate()
            self.log.insert("end", "\n[!] Process stopped by user.\n")

    def start_thread(self):
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        pkg = self.pkg_path.get()
        game = self.game_path.get()

        if not pkg or not os.path.exists(pkg):
            messagebox.showwarning("Warning", "Please select a valid PKG file.")
            return
        if not game:
            messagebox.showwarning("Warning", "Game Data path cannot be empty.")
            return

        self.install_btn.configure(state="disabled", text="INSTALLING...")
        self.stop_btn.configure(state="normal")
        self.log.delete("1.0", "end")

        try:
            # Clean environment for sub-AppImage execution
            env = os.environ.copy()
            env.pop('LD_LIBRARY_PATH', None)

            # Ensure internal extractor is executable
            if os.path.exists(self.appimage_bin):
                os.chmod(self.appimage_bin, 0o755)

            # Check PKG Type
            check = subprocess.run([self.appimage_bin, pkg, '--check-type'], capture_output=True, env=env)
            target = self.addon_path.get() if check.returncode == 103 else game
            
            self.log.insert("end", f"> Target: {target}\n> Initializing...\n\n")

            self.active_process = subprocess.Popen(
                ['nice', '-n', '10', self.appimage_bin, pkg, target],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env
            )

            for line in iter(self.active_process.stdout.readline, ''):
                self.log.insert("end", line)
                self.log.see("end")
                time.sleep(0.005)

            if self.active_process.wait() == 0:
                messagebox.showinfo("Done", "Successfully installed!")

        except Exception as e:
            self.log.insert("end", f"\n[CRITICAL ERROR] {str(e)}\n")
        finally:
            self.install_btn.configure(state="normal", text="START INSTALL")
            self.stop_btn.configure(state="disabled")
            self.active_process = None

if __name__ == "__main__":
    app = PKGInstaller()
    app.mainloop()