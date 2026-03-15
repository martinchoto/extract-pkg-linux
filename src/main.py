import customtkinter as ctk
import os
import subprocess
import threading
import json
import sys
import time
from plyer import filechooser
from tkinter import messagebox, PhotoImage


# this is for the app image builder 
# 
if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_ROOT

# config path for the settings
CONFIG_PATH = os.path.join(APP_ROOT, "config.json")

# helper method to get everything in a bundle
def get_bundle_path(rel_path):
    
    return os.path.join(BUNDLE_DIR, rel_path)

# app class and builder

class PKGInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PKG Installer Tool")
        self.geometry("850x780")
        self.configure(fg_color="#0a0f1e")

        # needs all the files in the project for the build to work
        self.appimage = get_bundle_path("pkg_extractor.AppImage")
        self.logo_path = get_bundle_path("logo.png")
        
        # these are the default paths for linux 
        # if you change them it is saved in the config.json
        
        self.pkg_path = ctk.StringVar()
        self.game_path = ctk.StringVar(value=os.path.expanduser("~/.local/share/shadPS4/user/game_data"))
        self.addon_path = ctk.StringVar(value=os.path.expanduser("~/.local/share/shadPS4/user/addcont"))

        # loads the config file
        self.load_config()
        
        self.setup_ui()
        self.set_linux_icon()
        
        # checks if there are active processes
        self.active_process = None



    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    if "game_path" in data: self.game_path.set(data["game_path"])
                    if "addon_path" in data: self.addon_path.set(data["addon_path"])
            except Exception as e:
                print(f"Load config failed: {e}")

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({
                    "game_path": self.game_path.get(),
                    "addon_path": self.addon_path.get()
                }, f, indent=4)
        except Exception as e:
            print(f"Save config failed: {e}")

    def set_linux_icon(self):
        if os.path.exists(self.logo_path):
            try:
                img = PhotoImage(file=self.logo_path)
                self.iconphoto(False, img)
            except:
                pass

    def setup_ui(self):
        # header of the app
        
        self.lbl_title = ctk.CTkLabel(self, text="PKG Installer Tool", font=ctk.CTkFont(family="Impact", size=44), text_color="#4db8ff")
        self.lbl_title.pack(pady=(30, 10))
        
        # rows for the files 
        
        self.create_row("SELECT PKG FILE", self.pkg_path, self.browse_pkg)
        self.create_row("GAME DATA LOCATION", self.game_path, lambda: self.browse_folder(self.game_path))
        self.create_row("DLC / ADDON LOCATION", self.addon_path, lambda: self.browse_folder(self.addon_path))


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

        # the works for the console
        self.log = ctk.CTkTextbox(self, height=280, fg_color="#010409", text_color="#00ffcc", font=("Monospace", 11))
        self.log.pack(padx=20, pady=10, fill="both", expand=True)

    def create_row(self, label, var, cmd):
        lbl = ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8892b0")
        lbl.pack(anchor="w", padx=60, pady=(15, 0))
        
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=60, pady=5)
        
        ctk.CTkEntry(f, textvariable=var, height=38, fg_color="#1b263b", border_color="#333").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(f, text="BROWSE", width=90, command=cmd).pack(side="right")

    def browse_pkg(self):
        p = filechooser.open_file(title="Select PKG file", filters=[("*.pkg")])
        if p: self.pkg_path.set(p[0])

    def browse_folder(self, var):
        p = filechooser.choose_dir(title="Select Folder")
        if p: 
            var.set(p[0])
            self.save_config()

    def kill_process(self):
        if self.active_process:
            self.active_process.terminate()
            self.log.insert("end", "\n[!] Process terminated by user.\n")
            self.log.see("end")


# should prevent freezing the application 
    def start_thread(self):
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        pkg = self.pkg_path.get()
        if not pkg or not os.path.exists(pkg):
            messagebox.showwarning("Warning", "Please select a valid PKG file.")
            return

        self.install_btn.configure(state="disabled", text="INSTALLING...")
        self.stop_btn.configure(state="normal")
        self.log.delete("1.0", "end")

        try:
            
            check = subprocess.run(['nice', '-n', '10', self.appimage, pkg, '--check-type'], capture_output=True)
            
            # if the code is 103 its an dlc or an addon
            target = self.addon_path.get() if check.returncode == 103 else self.game_path.get()
            self.log.insert("end", f"> Target: {target}\n> Starting extraction...\n\n")
            
            self.active_process = subprocess.Popen(
                ['nice', '-n', '10', self.appimage, pkg, target],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )

            # should fix the 100% of the cpu while you are installing the package
            while True:
                line = self.active_process.stdout.readline()
                if not line and self.active_process.poll() is not None:
                    break
                if line:
                    self.log.insert("end", line)
                    self.log.see("end")
                
                time.sleep(0.005)

            if self.active_process.returncode == 0:
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