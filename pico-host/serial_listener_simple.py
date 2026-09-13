#!/usr/bin/env python3
"""
Simple Serial Listener for Pico Commander (No external dependencies)
Reads from serial port using only Python standard library
"""

import sys
import time
import json
import os
from datetime import datetime


class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def read_serial_raw(port_path):
    """Read from serial port using raw file operations"""
    try:
        # Open serial port as binary file
        ser = open(port_path, 'rb', buffering=0)
        return ser
    except (IOError, OSError) as e:
        print(f"{Colors.RED}[Error] Cannot open {port_path}: {e}{Colors.END}")
        return None


def parse_line(line):
    """Try to parse as JSON or return as text"""
    line = line.strip()
    if not line:
        return None
    
    try:
        data = json.loads(line)
        if isinstance(data, dict) and 'event' in data:
            return ('event', data)
        return ('json', data)
    except:
        return ('text', line)


def main():
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("╔═══════════════════════════════════════════════════╗")
    print("║   Pico Serial Listener (Simple Version)          ║")
    print("╚═══════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # Check for port argument
    if len(sys.argv) < 2:
        print(f"{Colors.YELLOW}Usage: {sys.argv[0]} <PORT>{Colors.END}")
        print(f"\nExamples:")
        print(f"  Linux:   {sys.argv[0]} /dev/ttyACM1")
        print(f"  Windows: {sys.argv[0]} COM4")
        print(f"\n{Colors.CYAN}Available ports on Linux:{Colors.END}")
        
        # List available ports
        try:
            ports = [f for f in os.listdir('/dev') if f.startswith('ttyACM') or f.startswith('ttyUSB')]
            if ports:
                for p in ports:
                    print(f"  ├─ /dev/{p}")
            else:
                print(f"  └─ No ttyACM/ttyUSB devices found")
        except:
            pass
        
        sys.exit(1)
    
    port_path = sys.argv[1]
    
    print(f"{Colors.CYAN}[Serial] Opening {port_path}...{Colors.END}")
    ser = read_serial_raw(port_path)
    
    if not ser:
        sys.exit(1)
    
    print(f"{Colors.GREEN}[Serial] Connected! Listening for data...{Colors.END}")
    print(f"{Colors.YELLOW}{'─' * 60}{Colors.END}\n")
    
    message_count = 0
    byte_count = 0
    buffer = b''
    
    try:
        while True:
            # Read available bytes
            chunk = ser.read(1024)
            
            if chunk:
                buffer += chunk
                
                # Process complete lines
                while b'\n' in buffer:
                    line_bytes, buffer = buffer.split(b'\n', 1)
                    
                    message_count += 1
                    byte_count += len(line_bytes) + 1
                    
                    # Decode
                    try:
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                    except:
                        line = str(line_bytes)
                    
                    if not line:
                        continue
                    
                    # Timestamp
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    
                    # Parse
                    result = parse_line(line)
                    
                    if result:
                        data_type, data = result
                        
                        # Format output
                        print(f"{Colors.BOLD}[{timestamp}]{Colors.END} "
                              f"{Colors.BLUE}#{message_count}{Colors.END} "
                              f"{Colors.YELLOW}({len(line_bytes)}B){Colors.END} ", end='')
                        
                        if data_type == 'event':
                            print(f"{Colors.GREEN}[EVENT]{Colors.END} "
                                  f"{Colors.CYAN}{data.get('event', 'unknown')}{Colors.END}")
                            
                            if 'uptime' in data:
                                print(f"  ├─ uptime: {data['uptime']}s")
                            
                            extra = {k: v for k, v in data.items() if k not in ['event', 'uptime']}
                            if extra:
                                print(f"  └─ data: {json.dumps(extra)}")
                        
                        elif data_type == 'json':
                            print(f"{Colors.BLUE}[JSON]{Colors.END}")
                            print(f"  └─ {json.dumps(data)}")
                        
                        else:
                            print(f"[TEXT] {data}")
                        
                        # Show hex preview
                        hex_preview = ' '.join(f'{b:02x}' for b in line_bytes[:40])
                        if len(line_bytes) > 40:
                            hex_preview += "..."
                        print(f"  {Colors.CYAN}raw:{Colors.END} {hex_preview}\n")
            
            else:
                time.sleep(0.01)  # Small delay to avoid busy-wait
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}{'─' * 60}{Colors.END}")
        print(f"{Colors.BOLD}[Stats] Session Summary:{Colors.END}")
        print(f"  ├─ Messages: {message_count}")
        print(f"  └─ Bytes: {byte_count}")
        print(f"\n{Colors.GREEN}[Serial] Closed.{Colors.END}")
        ser.close()
    
    except Exception as e:
        print(f"\n{Colors.RED}[Error] {e}{Colors.END}")
        ser.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
