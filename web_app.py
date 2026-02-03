from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import os
import json
import sys
import threading
import queue
from io import StringIO
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'braill-ai-secret-key-2024'  # TODO: maybe change this later?

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

braill_instance = None
is_running = False
assistant_thread = None

# terminal to the web interface
# Took us forever to figure this out!
class WebOutputCapture:
    def __init__(self, socketio):
        self.socketio = socketio
        self.terminal = sys.__stdout__
        
    def write(self, text):
        self.terminal.write(text)
        self.terminal.flush()
        
        if text.strip():
            self.socketio.emit('terminal_output', {
                'text': text.strip(),
                'timestamp': time.time()
            })
    
    def flush(self):
        self.terminal.flush()


# Main page
@app.route('/')
def index():
    return render_template('index.html')


# save config
@app.route('/api/save-config', methods=['POST'])
def save_config():
    """Save API keys - this is where users put their Gemini and Mobilerun keys"""
    try:
        data = request.json
        
        # Save to session
        session['gemini_key'] = data.get('gemini_key')
        session['mobilerun_key'] = data.get('mobilerun_key')
        session['device_id'] = data.get('device_id')
        
        with open('.env', 'w') as f:
            f.write(f"GEMINI_API_KEY={data.get('gemini_key')}\n")
            f.write(f"MOBILERUN_KEY={data.get('mobilerun_key')}\n")
            f.write(f"DEVICE_ID={data.get('device_id')}\n")
        
        return jsonify({'success': True, 'message': 'Configuration saved!'})
    except Exception as e:
        print(f"Error saving config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# API endpoint to save user profile
@app.route('/api/save-profile', methods=['POST'])
def save_profile():
    """Save user profile - needed for emergency feature"""
    try:
        data = request.json
        
        session['user_profile'] = data
        
        # Save to JSON file
        with open('user_profile.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Profile saved for: {data.get('name')}")
        return jsonify({'success': True, 'message': 'Profile saved!'})
    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get-reminders', methods=['GET'])
def get_reminders():
    """Get all reminders"""
    try:
        if os.path.exists('reminders.json'):
            with open('reminders.json', 'r') as f:
                reminders = json.load(f)
                return jsonify({'success': True, 'reminders': reminders})
        return jsonify({'success': True, 'reminders': []})
    except Exception as e:
        print(f"Error getting reminders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/delete-reminder', methods=['POST'])
def delete_reminder():
    """Delete a specific reminder"""
    try:
        data = request.json
        time_to_delete = data.get('time')
        medicine_to_delete = data.get('medicine')
        
        if os.path.exists('reminders.json'):
            with open('reminders.json', 'r') as f:
                reminders = json.load(f)
            
            reminders = [r for r in reminders if not (r['time'] == time_to_delete and r['medicine'] == medicine_to_delete)]
            
            with open('reminders.json', 'w') as f:
                json.dump(reminders, f, indent=2)
            
            return jsonify({'success': True, 'message': 'Reminder deleted'})
        
        return jsonify({'success': False, 'error': 'No reminders file found'})
    except Exception as e:
        print(f"Error deleting reminder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get-notes', methods=['GET'])
def get_notes():
    """Get all notes"""
    try:
        if os.path.exists('notes.json'):
            with open('notes.json', 'r') as f:
                notes = json.load(f)
                return jsonify({'success': True, 'notes': notes})
        return jsonify({'success': True, 'notes': []})
    except Exception as e:
        print(f"Error getting notes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# webSoc
@socketio.on('connect')
def handle_connect():
    """When someone connects to the web app"""
    print("Client connected!")
    emit('status', {'message': 'Connected to BraillAI server'})


# Start
@socketio.on('start_assistant')
def start_assistant(data):
    """This starts the BraillAI voice assistant"""
    global braill_instance, is_running, assistant_thread
    
    try:
        # Check if already running
        if is_running:
            emit('error', {'message': 'Assistant is already running'})
            return
        
        print("Starting assistant...")
        
        # Get API
        gemini_key = session.get('gemini_key') or data.get('gemini_key')
        mobilerun_key = session.get('mobilerun_key') or data.get('mobilerun_key')
        device_id = session.get('device_id') or data.get('device_id')
        
        # Set environment variables
        os.environ['GEMINI_API_KEY'] = gemini_key
        os.environ['MOBILERUN_KEY'] = mobilerun_key
        os.environ['DEVICE_ID'] = device_id
        
        # Import BraillAI
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        sys.stdout = WebOutputCapture(socketio)
        
        from braill_ai_v2 import BraillAI
        
        braill_instance = BraillAI()
        
        # Load contacts if they exist
        try:
            if os.path.exists('contacts.json'):
                with open('contacts.json', 'r') as f:
                    contacts = json.load(f)
                    braill_instance.contacts = {c['name']: c['number'] for c in contacts}
                    print(f"Loaded {len(contacts)} contacts")
        except Exception as e:
            print(f"Couldn't load contacts: {e}")
        
        #user profile and emergency contact
        try:
            if os.path.exists('user_profile.json'):
                with open('user_profile.json', 'r') as f:
                    profile = json.load(f)
                    #update emergency contact
                    from braill_ai_v2 import EMERGENCY_CONTACT
                    EMERGENCY_CONTACT['name'] = profile.get('emergency_name', 'emergency')
                    EMERGENCY_CONTACT['number'] = profile.get('emergency_number', '')
                    print(f"Loaded profile for: {profile.get('name')}")
        except Exception as e:
            print(f"Couldn't load profile: {e}")
        
        is_running = True
        
        def run_assistant():
            try:
                braill_instance.run()
            except Exception as e:
                print(f"Assistant crashed: {e}")
                socketio.emit('error', {'message': f'Assistant error: {str(e)}'})
            finally:
                global is_running
                is_running = False
                socketio.emit('assistant_stopped', {})
        
        assistant_thread = threading.Thread(target=run_assistant, daemon=True)
        assistant_thread.start()
        
        emit('assistant_started', {'message': 'BraillAI is now running!'})
        
    except Exception as e:
        print(f"Failed to start assistant: {e}")
        emit('error', {'message': f'Failed to start: {str(e)}'})
        is_running = False


#stop
@socketio.on('stop_assistant')
def stop_assistant():
    """Stop the voice assistant"""
    global braill_instance, is_running, assistant_thread
    
    print("Stop button pressed - sending stop signal...")
    
    if braill_instance:
        braill_instance.trigger_stop()
        print("Stop signal sent to assistant")
    
    is_running = False
    
    emit('assistant_stopped', {'message': 'Assistant stopping...'})
    print("Stop command completed")


# quick action
@socketio.on('send_command')
def handle_command(data):
    """Execute commands from the quick action buttons"""
    global braill_instance, is_running
    
    if not braill_instance:
        emit('error', {'message': 'Assistant not running'})
        return
    
    command = data.get('command')
    print(f"Executing command: {command}")
    
    try:
        socketio.emit('terminal_output', {
            'text': f'[COMMAND] Executing: {command}',
            'timestamp': time.time()
        })
       
        def execute_command():
            try:
                #Pause main loop
                braill_instance.command_mode = True
                print(f"[COMMAND MODE] Pausing main loop for: {command}")
                
                if command == 'emergency':
                    print("EMERGENCY: Executing emergency call...")
                    
                    # user profile for emergency info
                    profile = None
                    try:
                        if os.path.exists('user_profile.json'):
                            with open('user_profile.json', 'r') as f:
                                profile = json.load(f)
                    except:
                        pass
                    
                    # dend profile info to frontend for alert display
                    if profile:
                        socketio.emit('show_emergency_alert', {
                            'name': profile.get('name', '—'),
                            'blood': profile.get('blood', '—'),
                            'address': profile.get('address', '—'),
                            'emergency_name': profile.get('emergency_name', '—'),
                            'emergency_number': profile.get('emergency_number', '—')
                        })
                    
                    braill_instance.emergency()
                    print("Emergency contact called!")
                    
                elif command == 'reminder':
                    braill_instance.add_reminder()
                    
                elif command == 'note':
                    braill_instance.save_note()
                    
                elif command == 'read_notes':
                    braill_instance.read_notes()
                
                # resume main loop
                print(f"[COMMAND MODE] Command completed, resuming main loop")
                braill_instance.command_mode = False
                
                socketio.emit('command_executed', {'command': command})
            except Exception as e:
                print(f"Command failed: {e}")
                braill_instance.command_mode = False
                socketio.emit('error', {'message': f'Command failed: {str(e)}'})
        
        cmd_thread = threading.Thread(target=execute_command, daemon=True)
        cmd_thread.start()
        
        emit('command_sent', {'command': command})
        
    except Exception as e:
        print(f"Error executing command: {e}")
        emit('error', {'message': f'Command error: {str(e)}'})


# update contacts
@socketio.on('update_contacts')
def update_contacts(data):
    """Save contacts to file"""
    global braill_instance
    
    contacts = data.get('contacts', [])
    
    try:
        with open('contacts.json', 'w') as f:
            json.dump(contacts, f, indent=2)
        
        if braill_instance:
            braill_instance.contacts = {c['name']: c['number'] for c in contacts}
        
        emit('contacts_updated', {'success': True})
        print(f"Updated contacts: {len(contacts)} total")
        
    except Exception as e:
        print(f"Failed to update contacts: {e}")
        emit('error', {'message': f'Failed to update contacts: {str(e)}'})

@socketio.on('quick_action')
def handle_quick_action(data):
    """Call or message a specific contact"""
    global braill_instance
    
    if not braill_instance:
        emit('error', {'message': 'Assistant not running'})
        return
    
    action = data.get('action')
    contact = data.get('contact')
    
    print(f"Quick action: {action} -> {contact}")
    
    try:
        socketio.emit('terminal_output', {
            'text': f'[QUICK ACTION] {action} -> {contact}',
            'timestamp': time.time()
        })
        
        def execute_action():
            try:
                braill_instance.command_mode = True
                print(f"[COMMAND MODE] Executing quick action: {action} -> {contact}")
                
                if action == 'call':
                    braill_instance.call_contact(contact)
                elif action == 'message':
                    braill_instance.send_message(contact)
                
                braill_instance.command_mode = False
                print(f"[COMMAND MODE] Quick action completed, resuming")
                
                socketio.emit('action_completed', {
                    'action': action,
                    'contact': contact
                })
                
            except Exception as e:
                print(f"Action failed: {e}")
                braill_instance.command_mode = False
                socketio.emit('error', {
                    'message': f'Action failed: {str(e)}'
                })
        
        action_thread = threading.Thread(target=execute_action, daemon=True)
        action_thread.start()
        
    except Exception as e:
        print(f"Quick action error: {e}")
        emit('error', {'message': f'Quick action error: {str(e)}'})


#starting
if __name__ == '__main__':
    print("\n" + "="*60)
    print(" BraillAI Web Server Starting...")
    print("---> Made by Team Droidians")
    print("="*60)
    print("\n Open your browser and go to: http://localhost:5000")
    print("\n" + "="*60 + "\n")
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
