import customtkinter as ctk
import socket
import threading
import psutil
import time
import tkinter as tk
from mcstatus import JavaServer
import re
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def clean_motd(raw):
    if not raw: return "No description"
    def parse(item):
        if isinstance(item, str): return item
        if isinstance(item, dict):
            res = item.get("text", "")
            for x in item.get("extra", []): res += parse(x)
            return res
        if isinstance(item, list): return "".join([parse(i) for i in item])
        return str(item)
    try: return re.sub(r'§[0-9a-fk-orx]', '', parse(raw)).strip()
    except: return str(raw)

class MCSMonitor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MCS Monitor")
        self.geometry("1000x780")
        self.configure(fg_color="#0B0E14")
        
        self.is_running = False
        self.thread_id = 0
        self.interval = 1.5
        self.hist_len = 120
        self.reset_data()
        self.current_mode = "launcher"
        
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True)
        self.show_launcher()

    def reset_data(self):
        self.cpu = [0] * self.hist_len
        self.mem = [0] * self.hist_len
        self.ping = [0] * self.hist_len
        self.players = [0] * self.hist_len
        self.max_pl = 20

    def clear(self):
        for w in self.main.winfo_children():
            w.pack_forget(); w.destroy()

    def show_launcher(self):
        self.clear(); self.current_mode = "launcher"
        f = ctk.CTkFrame(self.main, fg_color="transparent")
        f.pack(expand=True)
        ctk.CTkLabel(f, text="MCS MONITOR", font=("Segoe UI Variable Bold", 48), text_color="#58A6FF").pack(pady=30)
        btn_cfg = {"width": 280, "height": 55, "font": ("Segoe UI", 16, "bold")}
        ctk.CTkButton(f, text="SERVER MODE", command=self.init_server, **btn_cfg).pack(pady=10)
        ctk.CTkButton(f, text="CLIENT MODE", command=self.init_client, fg_color="#238636", **btn_cfg).pack(pady=10)

    def init_server(self):
        self.clear(); self.current_mode = "server"
        h = ctk.CTkFrame(self.main, fg_color="#151921", height=60); h.pack(fill="x")
        ctk.CTkLabel(h, text="BROADCASTER", font=("Segoe UI", 20, "bold")).pack(side="left", padx=25)
        self.port = ctk.CTkEntry(h, width=100, height=34); self.port.insert(0, "9999"); self.port.pack(side="right", padx=20)
        self.srv_btn = ctk.CTkButton(h, text="START", width=80, height=34, command=self.start_server); self.srv_btn.pack(side="right", padx=5)
        self.log = ctk.CTkTextbox(self.main, fg_color="#090C10", font=("Consolas", 13), text_color="#C9D1D9")
        self.log.pack(fill="both", expand=True, padx=25, pady=20)

    def log_msg(self, msg, tag="INFO"):
        pre = {"INFO": "[*]", "CONN": "[+]", "DISC": "[-]", "ERR": "[!]"}.get(tag, "[?]")
        self.after(0, lambda: self.log.insert("end", f"{pre} [{datetime.now():%H:%M:%S}] {msg}\n") or self.log.see("end"))

    def start_server(self):
        self.srv_btn.configure(state="disabled", text="LIVE")
        self.log_msg("Service initializing...", "INFO")
        threading.Thread(target=self.server_worker, args=(int(self.port.get()),), daemon=True).start()

    def server_worker(self, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0', port)); s.listen(5)
            self.log_msg(f"Listening on :{port}", "INFO")
            while True:
                conn, addr = s.accept()
                self.log_msg(f"Connected: {addr[0]}", "CONN")
                threading.Thread(target=self.server_push, args=(conn, addr), daemon=True).start()
        except Exception as e: self.log_msg(f"Error: {e}", "ERR")

    def server_push(self, conn, addr):
        try:
            while True:
                vm = psutil.virtual_memory()
                conn.send(f"{psutil.cpu_percent()}|{vm.percent}|{vm.used/1024**3:.2f}|{vm.total/1024**3:.2f}".encode())
                time.sleep(self.interval)
        except: self.log_msg(f"Disconnected: {addr[0]}", "DISC"); conn.close()

    def init_client(self):
        self.clear(); self.current_mode = "client"
        nav = ctk.CTkFrame(self.main, fg_color="#151921", height=85, corner_radius=0); nav.pack(fill="x", side="top")
        tlb = ctk.CTkFrame(nav, fg_color="transparent"); tlb.pack(side="left", padx=20)
        
        for t, v, d, w in [("IP", "tip", "", 160), ("MON", "mp", "9999", 70), ("MC", "mcp", "25565", 70)]:
            g = ctk.CTkFrame(tlb, fg_color="transparent"); g.pack(side="left", padx=8)
            ctk.CTkLabel(g, text=t, font=("Segoe UI", 12, "bold"), text_color="#8B949E").pack()
            e = ctk.CTkEntry(g, width=w, height=32, font=("Consolas", 15))
            if d: e.insert(0, d)
            setattr(self, v, e); e.bind("<Return>", lambda x: self.reload()); e.pack()
        
        self.btn = ctk.CTkButton(nav, text="ACTIVATE", command=self.toggle, width=120, height=40, font=("Segoe UI", 16, "bold"))
        self.btn.pack(side="right", padx=20)

        cnt = ctk.CTkScrollableFrame(self.main, fg_color="transparent", corner_radius=0); cnt.pack(fill="both", expand=True, padx=5, pady=5)
        sd = ctk.CTkFrame(cnt, fg_color="transparent", width=240); sd.pack(side="left", fill="y", padx=15)
        
        self.c_cpu = self.mk_card(sd, "CPU LOAD", "#58A6FF")
        self.c_mem = self.mk_card(sd, "RAM USAGE", "#D2A8FF")
        self.c_ping = self.mk_card(sd, "NETWORK PING", "#E3BC2F")
        self.c_mc = self.mk_card(sd, "MC ONLINE", "#2DB83D")
        
        ctk.CTkLabel(sd, text="ONLINE PLAYERS", font=("Segoe UI", 13, "bold"), text_color="#2DB83D").pack(pady=(10, 5))
        pb = ctk.CTkFrame(sd, fg_color="#151921", corner_radius=10, border_width=1, border_color="#30363D"); pb.pack(fill="both", expand=True)
        self.plist = ctk.CTkTextbox(pb, fg_color="transparent", font=("Consolas", 14), height=220); self.plist.pack(fill="both", expand=True, padx=5, pady=5)

        vis = ctk.CTkFrame(cnt, fg_color="#151921", corner_radius=12, border_width=1, border_color="#2D333B")
        vis.pack(side="right", fill="both", expand=True, padx=15, pady=10)
        
        mh = ctk.CTkFrame(vis, fg_color="#1C2128", height=50, corner_radius=10, border_width=1, border_color="#30363D")
        mh.pack(fill="x", padx=15, pady=12, ipady=5)
        self.motd = ctk.CTkLabel(mh, text="Ready", font=("Segoe UI", 16, "italic"), text_color="#E3BC2F"); self.motd.pack(expand=True, fill="both")
        
        self.g_cpu = self.mk_chart(vis, "CPU UTILIZATION (3m)", "#58A6FF")
        self.g_mem = self.mk_chart(vis, "MEMORY TELEMETRY (3m)", "#D2A8FF")
        self.g_ping = self.mk_chart(vis, "NETWORK LATENCY (3m)", "#E3BC2F")
        self.g_mc = self.mk_chart(vis, "PLAYER TREND (3m)", "#2DB83D")
        self.tip.focus_set()

    def mk_card(self, m, t, c):
        f = ctk.CTkFrame(m, fg_color="#151921", height=95, corner_radius=12, border_width=1, border_color="#30363D")
        f.pack(fill="x", pady=8); f.pack_propagate(False)
        ctk.CTkLabel(f, text=t, font=("Segoe UI", 11, "bold"), text_color=c).pack(pady=(6, 0))
        f.v, f.s = ctk.CTkLabel(f, text="--", font=("Segoe UI Variable Bold", 38)), ctk.CTkLabel(f, text="IDLE", font=("Segoe UI", 11), text_color="#555")
        f.v.pack(); f.s.pack()
        return f

    def mk_chart(self, m, t, c):
        f = ctk.CTkFrame(m, fg_color="transparent"); f.pack(fill="both", expand=True, padx=20, pady=1)
        ctk.CTkLabel(f, text=t, font=("Segoe UI", 11, "bold"), text_color="#8B949E").pack(anchor="w")
        can = tk.Canvas(f, bg="#151921", highlightthickness=0, height=95); can.pack(fill="both", expand=True)
        return can

    def start(self):
        self.is_running = False; self.thread_id += 1
        self.is_running = True; self.btn.configure(text="DEACTIVATE", fg_color="#E5534B")
        self.reset_data()
        threading.Thread(target=self.loop, args=(self.thread_id,), daemon=True).start()

    def stop(self):
        self.is_running = False; self.thread_id += 1
        self.btn.configure(text="ACTIVATE", fg_color="#1F6AA5")

    def toggle(self): self.stop() if self.is_running else self.start()
    def reload(self): self.btn.configure(text="RELOADING...", fg_color="#E5BC00"); self.after(100, self.start)

    def loop(self, tid):
        if tid != self.thread_id: return
        ip, mp, mcp = self.tip.get().strip(), int(self.mp.get()), int(self.mcp.get())
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try: s.settimeout(2.0); s.connect((ip, mp))
        except: pass

        while self.is_running:
            if tid != self.thread_id: break
            try: # System
                s.settimeout(1.0); raw = s.recv(1024).decode().split('|')
                if len(raw) >= 4:
                    self.cpu.pop(0); self.cpu.append(float(raw[0]))
                    self.mem.pop(0); self.mem.append(float(raw[1]))
                    self.after(0, lambda r=raw: self.upd_sys(r))
            except: 
                self.cpu.pop(0); self.cpu.append(0); self.mem.pop(0); self.mem.append(0)
                self.after(0, self.fail_sys)
            try: # MC
                st = JavaServer.lookup(f"{ip}:{mcp}", timeout=1.0).status()
                self.players.pop(0); self.players.append(st.players.online)
                self.ping.pop(0); self.ping.append(st.latency)
                self.max_pl = st.players.max
                self.after(0, lambda s=st, d=clean_motd(st.description): self.upd_mc(s, [p.name for p in s.players.sample] if s.players.sample else [], d))
            except:
                self.players.pop(0); self.players.append(0); self.ping.pop(0); self.ping.append(0)
                self.after(0, self.fail_mc)
            self.after(0, self.draw); time.sleep(self.interval)
        try: s.close()
        except: pass

    def upd_sys(self, r):
        self.c_cpu.v.configure(text=f"{r[0]}%", text_color="#FFF"); self.c_cpu.s.configure(text="ACTIVE", text_color="#555")
        self.c_mem.v.configure(text=f"{r[1]}%", text_color="#FFF"); self.c_mem.s.configure(text=f"{r[2]}G/{r[3]}G", text_color="#555")

    def fail_sys(self):
        self.c_cpu.v.configure(text="--", text_color="#DA3633"); self.c_cpu.s.configure(text="NO LINK", text_color="#DA3633")
        self.c_mem.v.configure(text="--", text_color="#DA3633"); self.c_mem.s.configure(text="OFFLINE", text_color="#DA3633")

    def upd_mc(self, s, n, d):
        p = int(s.latency)
        self.c_ping.v.configure(text=f"{p}ms", text_color="#FFF")
        c, t = ("#2EA043", "EXCELLENT") if p < 50 else ("#E3BC2F", "GOOD") if p < 150 else ("#DA3633", "POOR")
        self.c_ping.s.configure(text=t, text_color=c)
        self.c_mc.v.configure(text=f"{s.players.online}/{s.players.max}")
        self.motd.configure(text=d, text_color="#E3BC2F")
        self.plist.configure(state="normal"); self.plist.delete("0.0", "end")
        self.plist.insert("end", "\n".join([f" • {x}" for x in n]) if n else "No players"); self.plist.configure(state="disabled")

    def fail_mc(self):
        self.c_ping.v.configure(text="--", text_color="#DA3633"); self.c_ping.s.configure(text="OFFLINE", text_color="#DA3633")
        self.c_mc.v.configure(text="0/0")
        self.motd.configure(text="Server Offline / Closed", text_color="#DA3633")
        self.plist.configure(state="normal"); self.plist.delete("0.0", "end"); self.plist.insert("end", "Timeout"); self.plist.configure(state="disabled")

    def draw(self):
        if self.current_mode != "client" or not hasattr(self, "g_cpu"): return
        self.plot(self.g_cpu, self.cpu, "#58A6FF", 100)
        self.plot(self.g_mem, self.mem, "#D2A8FF", 100)
        self.plot(self.g_ping, self.ping, "#E3BC2F", max(max(self.ping), 100))
        self.plot(self.g_mc, self.players, "#2DB83D", self.max_pl)

    def plot(self, can, data, color, limit):
        can.update_idletasks(); w, h = can.winfo_width(), can.winfo_height()
        if w < 10: return
        can.delete("all"); limit = limit if limit > 0 else 1
        can.create_line(0, 5, w, 5, fill="#4A1515", dash=(4,4))
        for i in range(1, 4): y = 5 + (h-5)*(i/4); can.create_line(0, y, w, y, fill="#1C2128")
        pts = []; av_h = h - 15
        for i, v in enumerate(data): pts.extend([(i/(len(data)-1))*w, h - (v/limit*av_h) - 5])
        if len(pts) >= 4: can.create_line(pts, fill=color, width=2, smooth=True)

if __name__ == "__main__": MCSMonitor().mainloop()