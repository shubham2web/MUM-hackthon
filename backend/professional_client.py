#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The final, definitive client for the AI Debate Server.
This version loads the API key from the .env file for consistency
and displays the final analytics summary.
"""

import requests
import json
import argparse
import sys
import time
import itertools
import threading
import os
from sseclient import SSEClient
from colorama import Fore, Style, init as colorama_init
from datetime import datetime
from dotenv import load_dotenv

# --- Load the API key from the .env file for a single source of truth ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
# --------------------------------------------------------------------

class DebateClient:
    """Manages the connection, event processing, and output for an AI debate."""

    def __init__(self, topic, model, server_url, export_json=False, quiet=False):
        self.topic = topic
        self.model = model
        self.server_url = server_url
        self.export_json = export_json
        self.quiet = quiet

        self.api_key = API_KEY
        if not self.api_key:
            print(f"{Fore.RED}❌ Error: API_KEY not found in .env file. Please run 'python api_key_generator.py' first.{Style.RESET_ALL}")
            sys.exit(1)
            
        self.txt_filename = self._generate_filename("txt")
        self.json_filename = self._generate_filename("json") if export_json else None
        
        # State variables
        self.transcripts = {}
        self.event_log = []
        self.json_output = {}
        self.final_analytics = None # To store the final analytics data
        self.color_map = {}
        self.role_colors = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.BLUE]
        self.debate_start_time = None
        colorama_init(autoreset=True)

    def _generate_filename(self, extension):
        safe_topic = "".join(c for c in self.topic if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        return f"{safe_topic.replace(' ', '_')}_{timestamp}.{extension}"

    def _run_spinner(self, stop_spinner_event):
        spinner = itertools.cycle(['-', '/', '|', '\\'])
        while not stop_spinner_event.is_set():
            if not self.quiet:
                sys.stdout.write(f"\r{Style.BRIGHT}⏳ Connecting and waiting for server... {next(spinner)}")
                sys.stdout.flush()
            time.sleep(0.1)
        if not self.quiet:
            sys.stdout.write('\r' + ' ' * 60 + '\r')
            sys.stdout.flush()

    def run(self):
        print(f"{Style.BRIGHT}▶️  Connecting to {self.server_url} with topic: '{self.topic}'")
        print(f"📝 Saving text transcript to: {self.txt_filename}")
        if self.export_json:
            print(f"📄 Saving JSON transcript to: {self.json_filename}")

        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(target=self._run_spinner, args=(stop_spinner,))
        spinner_thread.start()

        try:
            headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
            payload = {"topic": self.topic, "model": self.model}
            response = requests.post(self.server_url, json=payload, headers=headers, stream=True, timeout=300)

            if response.status_code != 200:
                stop_spinner.set(); spinner_thread.join()
                self._handle_connection_error(response)
                return

            self._process_events(SSEClient(response), stop_spinner, spinner_thread)
        except requests.exceptions.ConnectionError:
            stop_spinner.set(); spinner_thread.join()
            print(f"\n{Fore.RED}❌ Connection Refused: Could not connect to {self.server_url}.")
            print(f"{Fore.YELLOW}   Is the server running? Please check and try again.")
        except Exception as e:
            stop_spinner.set(); spinner_thread.join()
            print(f"\n{Fore.RED}❌ An unexpected error occurred: {e}")

    def _handle_connection_error(self, response):
        print(f"\n{Fore.RED}❌ Connection Error: Server responded with status {response.status_code}")
        try:
            message = response.json().get("error", response.text.strip())
        except json.JSONDecodeError:
            message = response.text.strip()
        print(f"{Fore.YELLOW}   Server message: {message}")

    def _process_events(self, client, stop_spinner, spinner_thread):
        with open(self.txt_filename, 'w', encoding='utf-8') as f_txt:
            for event in client.events():
                if not stop_spinner.is_set():
                    stop_spinner.set(); spinner_thread.join()
                    self.debate_start_time = time.time()
                self._handle_event(event, f_txt)
        
        self._finalize_and_save()

    def _handle_event(self, event, file_handle):
        try:
            data = json.loads(event.data)
            self.event_log.append({"event": event.event, "data": data, "timestamp": time.time()})
        except json.JSONDecodeError:
            if not self.quiet: print(f"\n{Fore.YELLOW}⚠️  Received invalid data from server: {event.data}")
            return
        
        handler_map = {
            'metadata': self._handle_metadata,
            'start_role': self._handle_start_role,
            'token': self._handle_token,
            'end_role': self._handle_end_role,
            'analytics_metrics': self._handle_analytics, # New handler
            'end': self._handle_end,
            'error': self._handle_error
        }
        
        handler = handler_map.get(event.event)
        if handler:
            handler(data, file_handle)

    def _handle_metadata(self, data, f_txt):
        header = f"--- Debate Transcript ---\nTopic: {data.get('topic')}\nModel: {data.get('model_used')}\n-------------------------\n"
        if not self.quiet: print(Style.BRIGHT + header)
        f_txt.write(header + "\n")
        if self.export_json:
            self.json_output = {**data, "roles": {}, "event_log": []}

    def _handle_start_role(self, data, f_txt):
        role = data.get('role', 'Unknown')
        self.transcripts[role] = ""
        if role not in self.color_map: self.color_map[role] = self.role_colors[len(self.color_map) % len(self.role_colors)]
        elapsed = int(time.time() - self.debate_start_time)
        timestamp = f"[{elapsed // 60:02d}:{elapsed % 60:02d}]"
        if not self.quiet: print(f"\n\n{Style.DIM}{timestamp}{Style.RESET_ALL} {self.color_map[role]}{Style.BRIGHT}🎙️  {role.replace('_', ' ').title()}:{Style.RESET_ALL} ")

    def _handle_token(self, data, f_txt):
        role, token = data.get('role'), data.get('text', '')
        if role in self.transcripts:
            self.transcripts[role] += token
            if not self.quiet: print(token, end='', flush=True)

    def _handle_end_role(self, data, f_txt):
        role = data.get('role')
        if role in self.transcripts:
            full_statement = self.transcripts[role]
            f_txt.write(f"\n\n--- {role.replace('_', ' ').title()} ---\n{full_statement}")

    def _handle_analytics(self, data, f_txt):
        """Stores the final analytics to be displayed at the end."""
        self.final_analytics = data.get('metrics', {})
        f_txt.write("\n\n--- 📊 Analytics Report ---")
        f_txt.write(json.dumps(data, indent=2))

    def _handle_end(self, data, f_txt):
         if not self.quiet: print(f"\n\n{Style.BRIGHT}--- ✅ Debate Finished ---")
         f_txt.write("\n\n--- ✅ Debate Finished ---")
    
    def _handle_error(self, data, f_txt):
        error_message = f"\n\n{Fore.RED}❌ Server Error: {data.get('message')}{Style.RESET_ALL}"
        if not self.quiet: print(error_message)
        f_txt.write(error_message)

    def _finalize_and_save(self):
        """Saves reports and prints the final analytics summary."""
        if self.final_analytics and not self.quiet:
            print(f"\n\n{Style.BRIGHT}--- 📊 Final Analytics Summary ---{Style.RESET_ALL}")
            for key, value in self.final_analytics.items():
                if value is not None:
                    print(f"  - {key.replace('_', ' ').title():<25}{Fore.GREEN}{value:.3f}{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}-----------------------------------{Style.RESET_ALL}")

        if self.export_json:
            self.json_output["roles"] = self.transcripts
            self.json_output["event_log"] = self.event_log
            self.json_output["final_analytics"] = self.final_analytics
            
            if self.debate_start_time:
                duration = time.time() - self.debate_start_time
                self.json_output["debate_duration_seconds"] = round(duration, 2)
            
            self.json_output["turn_count"] = len(self.transcripts)

            with open(self.json_filename, 'w', encoding='utf-8') as f_json:
                json.dump(self.json_output, f_json, indent=2)
            print(f"📄 JSON transcript saved successfully to {self.json_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="The final client for the AI Debate Server.")
    parser.add_argument("topic", type=str, help="The topic for the debate.")
    parser.add_argument("--model", type=str, default="default-model", help="The AI model to request.")
    parser.add_argument("--url", type=str, default="http://localhost:5000/run_debate", help="The server URL.")
    parser.add_argument("--json", action="store_true", help="Save a structured JSON transcript.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppresses console output.")
    args = parser.parse_args()
    client = DebateClient(topic=args.topic, model=args.model, server_url=args.url, export_json=args.json, quiet=args.quiet)
    client.run()

