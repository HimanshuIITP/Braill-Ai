const socket = io();

let isAssistantRunning = false;
let currentConfig = null;
let userProfile = null;
let allProfiles = [];
let currentProfileId = null;

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function loadAllProfiles() {
    const saved = localStorage.getItem('braillai_profiles');
    if (saved) {
        allProfiles = JSON.parse(saved);
    }
    return allProfiles;
}

function saveAllProfiles() {
    localStorage.setItem('braillai_profiles', JSON.stringify(allProfiles));
}

function goToProfileSelector() {
    console.log('goToProfileSelector called');
    hideScreen('welcome-screen');
    hideScreen('dashboard-screen');
    hideScreen('profile-screen');
    hideScreen('setup-screen');
    showScreen('profile-selector-screen');
    console.log('Rendering profiles...');
    renderProfiles();
}

function renderProfiles() {
    console.log('renderProfiles called');
    const grid = document.getElementById('profiles-grid');
    console.log('Grid element:', grid);
    loadAllProfiles();
    console.log('All profiles:', allProfiles);
    
    if (allProfiles.length === 0) {
        grid.innerHTML = '<div class="empty-profiles">No profiles yet. Create one to get started!</div>';
        return;
    }
    
    grid.innerHTML = allProfiles.map(profile => `
        <div class="profile-card" onclick="selectProfile('${profile.id}')">
            <div class="profile-avatar">
                ${profile.name ? profile.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div class="profile-name">${escapeHtml(profile.name || 'User')}</div>
            <button class="delete-profile-btn" onclick="event.stopPropagation(); deleteProfile('${profile.id}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </button>
        </div>
    `).join('');
}

function createNewProfile() {
    const profileId = 'profile_' + Date.now();
    currentProfileId = profileId;
    
    const newProfile = {
        id: profileId,
        name: '',
        config: {},
        profile: {}
    };
    
    allProfiles.push(newProfile);
    saveAllProfiles();
    
    currentConfig = {};
    userProfile = {};
    
    clearAllForms();
    speakText('Creating a new profile. Let\'s set up your account.');
    goToSetup();
}

function clearAllForms() {
    const configForm = document.getElementById('config-form');
    if (configForm) configForm.reset();
    
    const profileForm = document.getElementById('profile-form');
    if (profileForm) profileForm.reset();
    
    document.getElementById('gemini-key').value = '';
    document.getElementById('mobilerun-key').value = '';
    document.getElementById('device-id').value = '';
    document.getElementById('user-name').value = '';
    document.getElementById('user-dob').value = '';
    document.getElementById('user-blood').value = '';
    document.getElementById('user-address').value = '';
    document.getElementById('emergency-name').value = '';
    document.getElementById('emergency-number').value = '';
}

function selectProfile(profileId) {
    currentProfileId = profileId;
    const profile = allProfiles.find(p => p.id === profileId);
    
    if (profile) {
        currentConfig = profile.config || {};
        userProfile = profile.profile || {};
        
        localStorage.setItem('braillai_config', JSON.stringify(currentConfig));
        localStorage.setItem('braillai_profile', JSON.stringify(userProfile));
        
        const name = userProfile.name || 'User';
        speakText(`Welcome back, ${name}!`);
        
        if (currentConfig.gemini_key && userProfile.name) {
            goToDashboard();
        } else if (currentConfig.gemini_key) {
            goToProfile();
        } else {
            goToSetup();
        }
    }
}

function deleteProfile(profileId) {
    if (confirm('Delete this profile? This cannot be undone.')) {
        allProfiles = allProfiles.filter(p => p.id !== profileId);
        saveAllProfiles();
        renderProfiles();
        showNotification('Profile deleted', 'success');
    }
}

function openProfileSwitcher() {
    const modal = document.getElementById('profile-switcher-modal');
    modal.classList.add('active');
    renderProfileSwitcher();
}

function closeProfileSwitcher() {
    const modal = document.getElementById('profile-switcher-modal');
    modal.classList.remove('active');
}

function renderProfileSwitcher() {
    const list = document.getElementById('profile-switcher-list');
    loadAllProfiles();
    
    if (allProfiles.length === 0) {
        list.innerHTML = '<div class="empty-state">No profiles available</div>';
        return;
    }
    
    list.innerHTML = allProfiles.map(profile => `
        <div class="profile-switcher-card ${profile.id === currentProfileId ? 'active' : ''}" onclick="switchToProfile('${profile.id}')">
            <div class="profile-switcher-avatar">
                ${profile.name ? profile.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div class="profile-switcher-info">
                <div class="profile-switcher-name">${escapeHtml(profile.name || 'User')}</div>
                ${profile.id === currentProfileId ? '<div class="profile-switcher-badge">Current</div>' : ''}
            </div>
            ${profile.id === currentProfileId ? '<div class="profile-switcher-check">✓</div>' : ''}
        </div>
    `).join('');
}

function switchToProfile(profileId) {
    if (profileId === currentProfileId) {
        closeProfileSwitcher();
        return;
    }
    
    selectProfile(profileId);
    closeProfileSwitcher();
    showNotification('Profile switched!', 'success');
}

function createNewProfileFromSwitcher() {
    closeProfileSwitcher();
    createNewProfile();
}

function triggerFloatingSOS() {
    const sosBtn = document.getElementById('floating-sos');
    sosBtn.classList.add('triggered');
    
    speakText('Emergency SOS activated! Calling your emergency contact now. Help is on the way.');
    showNotification('🚨 Emergency SOS Activated!', 'error');
    
    sendCommand('emergency');
    
    setTimeout(() => {
        sosBtn.classList.remove('triggered');
    }, 5000);
}

function updateDashboardSummary() {
    const now = new Date();
    
    const dateStr = now.toLocaleDateString('en-US', { 
        weekday: 'long', 
        month: 'short', 
        day: 'numeric' 
    });
    document.getElementById('summary-date').textContent = dateStr;
    
    fetch('/api/get-reminders')
        .then(r => r.json())
        .then(data => {
            const reminders = data.reminders || [];
            const todayReminders = reminders.filter(r => !r.last_triggered || r.last_triggered !== now.toDateString());
            document.getElementById('summary-reminders').textContent = todayReminders.length;
        })
        .catch(() => {
            document.getElementById('summary-reminders').textContent = '0';
        });
    
    fetch('/api/get-notes')
        .then(r => r.json())
        .then(data => {
            const notes = data.notes || [];
            document.getElementById('summary-notes').textContent = notes.length;
        })
        .catch(() => {
            document.getElementById('summary-notes').textContent = '0';
        });
    
    updateFontToggleStatus();
}

function toggleLargeFont() {
    document.body.classList.toggle('large-font');
    const isLarge = document.body.classList.contains('large-font');
    
    localStorage.setItem('largeFont', isLarge);
    updateFontToggleStatus();
    
    speakText(isLarge ? 'Large font enabled' : 'Large font disabled');
    showNotification(isLarge ? '🔤 Large Font Enabled' : 'Large Font Disabled', 'success');
}

function updateFontToggleStatus() {
    const isLarge = document.body.classList.contains('large-font');
    const statusEl = document.getElementById('font-toggle-status');
    const indicatorEl = document.getElementById('font-toggle-indicator');
    
    if (statusEl) {
        statusEl.textContent = isLarge ? 'ON' : 'OFF';
        statusEl.style.color = isLarge ? '#22c55e' : '';
    }
    
    if (indicatorEl) {
        if (isLarge) {
            indicatorEl.classList.add('active');
        } else {
            indicatorEl.classList.remove('active');
        }
    }
}

function loadReminders() {
    fetch('/api/get-reminders')
        .then(r => r.json())
        .then(data => {
            const reminders = data.reminders || [];
            renderRemindersList(reminders);
        })
        .catch(error => {
            console.error('Error loading reminders:', error);
            document.getElementById('reminders-list').innerHTML = '<div class="empty-state">Error loading reminders</div>';
        });
}

function renderRemindersList(reminders) {
    const container = document.getElementById('reminders-list');
    
    if (reminders.length === 0) {
        container.innerHTML = '<div class="empty-state">No reminders set yet</div>';
        return;
    }
    
    container.innerHTML = reminders.map(reminder => {
        const [hour, minute] = reminder.time.split(':');
        const hourNum = parseInt(hour);
        const displayHour = hourNum > 12 ? hourNum - 12 : (hourNum === 0 ? 12 : hourNum);
        const ampm = hourNum >= 12 ? 'PM' : 'AM';
        const timeDisplay = `${displayHour}:${minute} ${ampm}`;
        
        return `
            <div class="reminder-item">
                <div class="reminder-time">⏰ ${timeDisplay}</div>
                <div class="reminder-medicine">${escapeHtml(reminder.medicine)}</div>
                <button class="reminder-delete" onclick="deleteReminder('${reminder.time}', '${escapeHtml(reminder.medicine)}')" title="Delete">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

function deleteReminder(time, medicine) {
    if (confirm(`Delete reminder for ${medicine} at ${time}?`)) {
        fetch('/api/delete-reminder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time, medicine })
        })
        .then(r => r.json())
        .then(result => {
            if (result.success) {
                showNotification('Reminder deleted', 'success');
                loadReminders();
                updateDashboardSummary();
            } else {
                showNotification('Failed to delete reminder', 'error');
            }
        })
        .catch(error => {
            console.error('Error deleting reminder:', error);
            showNotification('Error deleting reminder', 'error');
        });
    }
}

function speakText(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.volume = 1;
        window.speechSynthesis.speak(utterance);
    }
}

function announceScreen(screenId) {
    const announcements = {
        'welcome-screen': 'Welcome to BraillAI. Your voice-powered assistant for independence. Press Get Started to begin.',
        'profile-selector-screen': 'Select your profile or create a new one.',
        'setup-screen': 'Let\'s get you set up. We need your API keys to connect BraillAI to your phone.',
        'profile-screen': 'Please enter your personal information and emergency contact details.',
        'dashboard-screen': 'Welcome to your dashboard. You can now use voice commands, set reminders, or call your contacts.'
    };
    
    const announcement = announcements[screenId];
    if (announcement) {
        setTimeout(() => {
            speakText(announcement);
        }, 500);
    }
}



function saveCurrentProfile() {
    if (currentProfileId) {
        const profileIndex = allProfiles.findIndex(p => p.id === currentProfileId);
        if (profileIndex !== -1) {
            allProfiles[profileIndex].config = currentConfig;
            allProfiles[profileIndex].profile = userProfile;
            allProfiles[profileIndex].name = userProfile.name || 'User';
            saveAllProfiles();
        }
    }
}


function goToSetup() {
    hideScreen('welcome-screen');
    hideScreen('dashboard-screen');
    hideScreen('profile-screen');
    hideScreen('profile-selector-screen');
    showScreen('setup-screen');
    
    if (currentConfig) {
        document.getElementById('gemini-key').value = currentConfig.gemini_key || '';
        document.getElementById('mobilerun-key').value = currentConfig.mobilerun_key || '';
        document.getElementById('device-id').value = currentConfig.device_id || '';
    }
}

function goToWelcome() {
    hideScreen('setup-screen');
    hideScreen('dashboard-screen');
    hideScreen('profile-screen');
    hideScreen('profile-selector-screen');
    showScreen('welcome-screen');
}

function goToProfile() {
    hideScreen('welcome-screen');
    hideScreen('dashboard-screen');
    hideScreen('setup-screen');
    hideScreen('profile-selector-screen');
    showScreen('profile-screen');
    
    if (userProfile) {
        document.getElementById('user-name').value = userProfile.name || '';
        document.getElementById('user-dob').value = userProfile.dob || '';
        document.getElementById('user-blood').value = userProfile.blood || '';
        document.getElementById('user-address').value = userProfile.address || '';
        document.getElementById('emergency-name').value = userProfile.emergency_name || '';
        document.getElementById('emergency-number').value = userProfile.emergency_number || '';
    }
}

function goToDashboard() {
    hideScreen('welcome-screen');
    hideScreen('setup-screen');
    hideScreen('profile-screen');
    hideScreen('profile-selector-screen');
    showScreen('dashboard-screen');
    updateGreeting();
    
    setTimeout(() => {
        updateDashboardSummary();
        loadReminders();
    }, 300);
}

function showScreen(screenId) {
    const screen = document.getElementById(screenId);
    if (screen) {
        setTimeout(() => {
            screen.classList.add('active');
            announceScreen(screenId);
        }, 100);
    }
}

function hideScreen(screenId) {
    const screen = document.getElementById(screenId);
    if (screen) {
        screen.classList.remove('active');
    }
}


function updateGreeting() {
    const greetingEl = document.getElementById('user-greeting');
    if (userProfile && userProfile.name) {
        const hour = new Date().getHours();
        let greeting = 'Hello';
    
        if (hour < 12) greeting = 'Good Morning';
        else if (hour < 17) greeting = 'Good Afternoon';
        else greeting = 'Good Evening';
        
        greetingEl.textContent = `${greeting}, ${userProfile.name.split(' ')[0]}`;
    } else {
        greetingEl.textContent = 'Hello, User';
    }
}

function showEmergencyAlert() {
    const alert = document.getElementById('emergency-alert');
    alert.style.display = 'block';
    
    if (userProfile) {
        document.getElementById('alert-name').textContent = userProfile.name || '—';
        document.getElementById('alert-blood').textContent = userProfile.blood || '—';
        document.getElementById('alert-address').textContent = userProfile.address || '—';
        document.getElementById('alert-contact').textContent = 
            `${userProfile.emergency_name} (${userProfile.emergency_number})` || '—';
    }
    
    setTimeout(() => {
        hideEmergencyAlert();
    }, 30000);
}

function hideEmergencyAlert() {
    const alert = document.getElementById('emergency-alert');
    alert.style.display = 'none';
}


let voiceSetupEnabled = false;
let currentRecognition = null;

function checkVoiceSupport() {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
}

function toggleVoiceSetup() {
    if (!checkVoiceSupport()) {
        showNotification('Voice input not supported in your browser. Try Chrome!', 'error');
        return;
    }
    
    voiceSetupEnabled = !voiceSetupEnabled;
    const btn = document.getElementById('voice-setup-btn') || document.getElementById('voice-profile-btn');
    
    if (voiceSetupEnabled) {
        btn.classList.add('active');
        btn.querySelector('span').textContent = 'Voice Input Enabled ✓';
        showNotification('Voice input enabled! Click microphone buttons to speak', 'success');
    } else {
        btn.classList.remove('active');
        btn.querySelector('span').textContent = 'Enable Voice Input';
        showNotification('Voice input disabled', 'info');
    }
}

function startVoiceInput(fieldId) {
    if (!checkVoiceSupport()) {
        showNotification('Voice input not supported. Use keyboard instead.', 'error');
        return;
    }
    
    const input = document.getElementById(fieldId);
    const btn = event.target.closest('.voice-input-btn');

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    
    btn.classList.add('listening');
    showNotification('🎤 Listening... Speak now!', 'info');
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        
        if (input.tagName.toLowerCase() === 'textarea') {
            if (input.value && input.value.trim()) {
                input.value += ' ' + transcript;
            } else {
                input.value = transcript;
            }
        } else {
            input.value = transcript;
        }
        
        btn.classList.remove('listening');
        btn.classList.add('success');
        
        const shortText = transcript.length > 50 ? transcript.substring(0, 50) + '...' : transcript;
        showNotification(`Got it: "${shortText}"`, 'success');
        
        setTimeout(() => {
            btn.classList.remove('success');
        }, 2000);
    };
    
    recognition.onerror = (event) => {
        btn.classList.remove('listening');
        console.error('Speech recognition error:', event.error);
        
        if (event.error === 'no-speech') {
            showNotification('No speech detected. Try again!', 'error');
        } else if (event.error === 'not-allowed') {
            showNotification('Microphone access denied. Enable it in browser settings.', 'error');
        } else {
            showNotification('Voice input error. Try typing instead.', 'error');
        }
    };
    
    recognition.onend = () => {
        btn.classList.remove('listening');
    };
    
    try {
        recognition.start();
        currentRecognition = recognition;
    } catch (error) {
        btn.classList.remove('listening');
        showNotification('Could not start voice input. Try again!', 'error');
        console.error('Recognition start error:', error);
    }
}

function stopVoiceInput() {
    if (currentRecognition) {
        currentRecognition.stop();
        currentRecognition = null;
    }
}


document.getElementById('config-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const config = {
        gemini_key: formData.get('gemini_key'),
        mobilerun_key: formData.get('mobilerun_key'),
        device_id: formData.get('device_id')
    };
    
    try {
        const response = await fetch('/api/save-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentConfig = config;
            localStorage.setItem('braillai_config', JSON.stringify(config));
            saveCurrentProfile();
            showNotification('Configuration saved!', 'success');
            goToProfile();
        } else {
            showNotification('Failed to save configuration', 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showNotification('Error saving configuration', 'error');
    }
});


document.getElementById('profile-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const profile = {
        name: formData.get('user_name'),
        dob: formData.get('user_dob'),
        blood: formData.get('user_blood'),
        address: formData.get('user_address'),
        emergency_name: formData.get('emergency_name'),
        emergency_number: formData.get('emergency_number')
    };
    
    try {
        const response = await fetch('/api/save-profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(profile)
        });
        
        const result = await response.json();
        
        if (result.success) {
            userProfile = profile;
            localStorage.setItem('braillai_profile', JSON.stringify(profile));
            saveCurrentProfile();
            showNotification('Profile saved!', 'success');
            setTimeout(() => {
                goToDashboard();
            }, 800);
        } else {
            showNotification('Failed to save profile', 'error');
        }
    } catch (error) {
        console.error('Error saving profile:', error);
        showNotification('Error saving profile', 'error');
    }
});


function startAssistant() {
    if (isAssistantRunning) {
        showNotification('Assistant is already running', 'error');
        return;
    }
    

    const feed = document.getElementById('conversation-feed');
    feed.innerHTML = '<div class="system-message"><p>🎙️ Starting BraillAI...</p></div>';
    
    document.getElementById('start-btn').style.display = 'none';
    document.getElementById('stop-btn').style.display = 'flex';
    updateStatus('Starting...', false);
    
    socket.emit('start_assistant', currentConfig || {});
}

function stopAssistant() {
    document.getElementById('start-btn').style.display = 'flex';
    document.getElementById('stop-btn').style.display = 'none';
    updateStatus('Stopping...', false);
    
    addSystemMessage('⏹️ Stopping assistant...');
    showNotification('Stopping assistant...', 'info');
    

    socket.emit('stop_assistant');
    
    setTimeout(() => {
        isAssistantRunning = false;
        updateStatus('Stopped', false);
        addSystemMessage('Assistant stopped');
    }, 2000);
}


function sendCommand(command) {
    if (!isAssistantRunning) {
        showNotification('Please start the assistant first', 'error');
        return;
    }
    
    const commandNames = {
        'emergency': '🚨 Emergency Call',
        'reminder': '⏰ Set Reminder',
        'note': '📝 Save Note',
        'read_notes': '📖 Read Notes',
        'call': '📞 Make Call',
        'message': '💬 Send Message'
    };
    
    if (command === 'emergency') {

        if (!userProfile) {
            showNotification('Please complete your profile first for emergency features!', 'error');
            setTimeout(() => goToProfile(), 1000);
            return;
        }
        
        addSystemMessage('▶ Emergency: Calling emergency contact...');
        showNotification('🚨 EMERGENCY ACTIVATED', 'error');
        socket.emit('send_command', { command: command });
        return;
    }
    

    if (command === 'call' || command === 'message') {
        openActionModal(command);
        return;
    }
    
    showNotification(`Executing: ${commandNames[command]}`, 'info');
    addSystemMessage(`▶ Quick Action: ${commandNames[command]}`);
    
    socket.emit('send_command', { command: command });
}

// web soc

socket.on('connect', () => {
    console.log('Connected to server');
    updateStatus('Connected', false);
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateStatus('Disconnected', false);
    isAssistantRunning = false;
});

socket.on('status', (data) => {
    console.log('Status:', data.message);
});

socket.on('assistant_started', (data) => {
    isAssistantRunning = true;
    updateStatus('Running', true);
    showNotification('BraillAI started successfully!', 'success');
    addSystemMessage('BraillAI is now listening...');
    document.body.classList.add('assistant-active');
});

socket.on('assistant_stopped', (data) => {
    isAssistantRunning = false;
    updateStatus('Stopped', false);
    document.getElementById('start-btn').style.display = 'flex';
    document.getElementById('stop-btn').style.display = 'none';
    addSystemMessage('Assistant stopped');
    document.body.classList.remove('assistant-active');
});

socket.on('terminal_output', (data) => {

    const text = data.text;
    
    if (text.includes('[COMMAND] Executing: emergency') || 
        text.includes('Emergency contact called') ||
        text.includes('Calling emergency contact')) {
        showEmergencyAlert();
    }
    
    if (text.includes('Listening...')) {
        updateListeningStatus(true);
    } else if (text.includes('You said:')) {
        updateListeningStatus(false);
        const userText = text.replace('You said:', '').trim();
        addUserMessage(userText);
    } else if (text.includes('Braill-AI:')) {
        const aiText = text.replace('Braill-AI:', '').trim();
        addAIMessage(aiText);
    } else if (text.includes('[') && text.includes(']')) {
        addSystemMessage(text);
    } else if (text.trim().length > 0) {
        addTerminalOutput(text);
    }
});

socket.on('command_sent', (data) => {
    addSystemMessage(`Command sent: ${data.command}`);
});

socket.on('command_executed', (data) => {
    showNotification(`Command completed: ${data.command}`, 'success');
});

socket.on('show_emergency_alert', (data) => {
    const alert = document.getElementById('emergency-alert');
    alert.style.display = 'block';
    
    document.getElementById('alert-name').textContent = data.name || '—';
    document.getElementById('alert-blood').textContent = data.blood || '—';
    document.getElementById('alert-address').textContent = data.address || '—';
    document.getElementById('alert-contact').textContent = 
        `${data.emergency_name} (${data.emergency_number})` || '—';
    
    setTimeout(() => {
        hideEmergencyAlert();
    }, 30000);
});

socket.on('request_input', (data) => {
    addSystemMessage(`Input needed: ${data.message}`);
});

socket.on('error', (data) => {
    showNotification(data.message, 'error');
    addSystemMessage(`Error: ${data.message}`);
});


function updateStatus(text, active) {
    const badge = document.getElementById('status-badge');
    const statusText = badge.querySelector('.status-text');
    
    statusText.textContent = text;
    
    if (active) {
        badge.classList.add('active');
    } else {
        badge.classList.remove('active');
    }
}

function updateListeningStatus(isListening) {
    const indicator = document.getElementById('listening-indicator');
    
    if (isListening) {
        indicator.classList.add('active');
        indicator.innerHTML = '<span class="pulse"></span> Listening...';
    } else {
        indicator.classList.remove('active');
        indicator.innerHTML = '<span class="pulse"></span> Ready to listen';
    }
}


function addUserMessage(text) {
    const feed = document.getElementById('conversation-feed');
    const message = document.createElement('div');
    message.className = 'user-message';
    message.innerHTML = `
        <div class="message-label">You</div>
        <p>${escapeHtml(text)}</p>
    `;
    feed.appendChild(message);
    scrollToBottom(feed);
}

function addAIMessage(text) {
    const feed = document.getElementById('conversation-feed');
    const message = document.createElement('div');
    message.className = 'ai-message';
    message.innerHTML = `
        <div class="message-label">BraillAI</div>
        <p>${escapeHtml(text)}</p>
    `;
    feed.appendChild(message);
    scrollToBottom(feed);
}

function addSystemMessage(text) {
    const feed = document.getElementById('conversation-feed');
    const message = document.createElement('div');
    message.className = 'system-message';
    message.innerHTML = `<p>${escapeHtml(text)}</p>`;
    feed.appendChild(message);
    scrollToBottom(feed);
}

function addTerminalOutput(text) {
    const feed = document.getElementById('conversation-feed');
    const message = document.createElement('div');
    message.className = 'system-message';
    message.style.opacity = '0.7';
    message.innerHTML = `<p style="font-size: 0.85rem;">${escapeHtml(text)}</p>`;
    feed.appendChild(message);
    scrollToBottom(feed);
}

function scrollToBottom(element) {
    element.scrollTop = element.scrollHeight;
}

// notifications

function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            container.removeChild(notification);
        }, 300);
    }, 4000);
}

// util

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

//init

document.addEventListener('DOMContentLoaded', () => {
    console.log('BraillAI Web Interface Loaded');
    
    // Load contacts
    loadContacts();
    
    const savedConfig = localStorage.getItem('braillai_config');
    if (savedConfig) {
        currentConfig = JSON.parse(savedConfig);
        // Auto-fill form if on setup screen
        const form = document.getElementById('config-form');
        if (form && currentConfig) {
            document.getElementById('gemini-key').value = currentConfig.gemini_key || '';
            document.getElementById('mobilerun-key').value = currentConfig.mobilerun_key || '';
            document.getElementById('device-id').value = currentConfig.device_id || '';
        }
    }
});

document.getElementById('config-form')?.addEventListener('input', (e) => {
    const formData = new FormData(e.target.form);
    const config = {
        gemini_key: formData.get('gemini_key'),
        mobilerun_key: formData.get('mobilerun_key'),
        device_id: formData.get('device_id')
    };
    localStorage.setItem('braillai_config', JSON.stringify(config));
});

//contact

let contacts = [];

function loadContacts() {
    const saved = localStorage.getItem('braillai_contacts');
    if (saved) {
        contacts = JSON.parse(saved);
        renderContacts();
    }
}

function saveContacts() {
    localStorage.setItem('braillai_contacts', JSON.stringify(contacts));
}

function openContactModal() {
  
    const modal = document.getElementById('contact-modal');
    modal.classList.add('active');
    renderContacts();
}

function closeContactModal() {
    const modal = document.getElementById('contact-modal');
    modal.classList.remove('active');
}

function addContact(event) {
    event.preventDefault(); 
    
    const name = document.getElementById('contact-name').value.trim().toLowerCase();
    const number = document.getElementById('contact-number').value.trim();
    
    if (!name || !number) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    if (contacts.some(c => c.name === name)) {
        showNotification('Contact with this name already exists', 'error');
        return;
    }
    
    contacts.push({ name, number });
    saveContacts();
    renderContacts();
    
    socket.emit('update_contacts', { contacts });
    
    document.getElementById('contact-name').value = '';
    document.getElementById('contact-number').value = '';
    
    showNotification(`Contact "${name}" added successfully!`, 'success');
}

function deleteContact(name) {
    if (confirm(`Delete contact "${name}"?`)) {
        contacts = contacts.filter(c => c.name !== name);
        saveContacts();
        renderContacts();
        
        socket.emit('update_contacts', { contacts });
        
        showNotification(`Contact "${name}" deleted`, 'success');
    }
}

function renderContacts() {
    const container = document.getElementById('contacts-list');
    
    if (contacts.length === 0) {
        container.innerHTML = '<div class="empty-state">No contacts yet. Add one above!</div>';
        return;
    }
    
    container.innerHTML = contacts.map(contact => `
        <div class="contact-card">
            <div class="contact-info">
                <div class="contact-name">${escapeHtml(contact.name)}</div>
                <div class="contact-number">${escapeHtml(contact.number)}</div>
            </div>
            <div class="contact-actions">
                <button class="contact-btn" onclick="quickCall('${escapeHtml(contact.name)}')" title="Call">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                        <path d="M22 16.92V19.92C22 20.4583 21.7587 20.9717 21.3346 21.3303C20.9106 21.6889 20.3467 21.8581 19.8082 21.7961C16.5408 21.3745 13.4389 20.1455 10.7843 18.2154C8.36163 16.4727 6.36781 14.1789 4.97843 11.5154C3.04943 8.68925 1.88353 5.48127 1.56843 2.13539C1.51166 1.56753 1.67455 0.992632 2.02009 0.544764C2.36564 0.096896 2.86381 -0.134819 3.38843 -0.114393H6.38843C7.22788 -0.123079 7.94171 0.443683 8.06843 1.20539C8.18629 2.01674 8.39484 2.81519 8.68843 3.58539C8.91843 4.18539 8.77843 4.85539 8.33843 5.29539L7.08843 6.54539C8.67743 9.11539 10.8984 11.3354 13.4684 12.9254L14.7184 11.6754C15.1584 11.2354 15.8284 11.0954 16.4284 11.3254C17.1986 11.619 17.9971 11.8275 18.8084 11.9454C19.585 12.0739 20.1625 12.8063 20.1484 13.6654V16.9254L22 16.92Z" stroke="currentColor" stroke-width="2"/>
                    </svg>
                </button>
                <button class="contact-btn" onclick="quickMessage('${escapeHtml(contact.name)}')" title="Message">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                        <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2"/>
                    </svg>
                </button>
                <button class="contact-btn delete" onclick="deleteContact('${escapeHtml(contact.name)}')" title="Delete">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                        <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                        <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function quickCall(contactName) {
    closeContactModal();
    showNotification(`Calling ${contactName}...`, 'info');
    socket.emit('quick_action', { action: 'call', contact: contactName });
}

function quickMessage(contactName) {
    closeContactModal();
    showNotification(`Opening message to ${contactName}...`, 'info');
    socket.emit('quick_action', { action: 'message', contact: contactName });
}

//action

let currentAction = null;

function openActionModal(action) {
    if (contacts.length === 0) {
        showNotification('No contacts available. Add contacts first!', 'error');
        openContactModal();
        return;
    }
    
    currentAction = action;
    const modal = document.getElementById('action-modal');
    const title = document.getElementById('action-modal-title');
    
    if (action === 'call') {
        title.textContent = '📞 Select Contact to Call';
    } else if (action === 'message') {
        title.textContent = '💬 Select Contact to Message';
    }
    
    renderActionContacts();
    modal.classList.add('active');
}

function closeActionModal() {
    const modal = document.getElementById('action-modal');
    modal.classList.remove('active');
    currentAction = null;
}

function renderActionContacts() {
    const container = document.getElementById('action-contacts-list');
    
    if (contacts.length === 0) {
        container.innerHTML = '<div class="empty-state">No contacts available</div>';
        return;
    }
    
    container.innerHTML = contacts.map(contact => `
        <div class="action-contact-card" onclick="selectContact('${escapeHtml(contact.name)}')">
            <div class="action-contact-icon">
                ${contact.name.charAt(0).toUpperCase()}
            </div>
            <div class="action-contact-info">
                <div class="action-contact-name">${escapeHtml(contact.name)}</div>
                <div class="action-contact-number">${escapeHtml(contact.number)}</div>
            </div>
        </div>
    `).join('');
}

function selectContact(contactName) {
    closeActionModal();
    
    if (currentAction === 'call') {
        showNotification(`Calling ${contactName}...`, 'info');
        socket.emit('quick_action', { action: 'call', contact: contactName });
    } else if (currentAction === 'message') {
        showNotification(`Messaging ${contactName}...`, 'info');
        socket.emit('quick_action', { action: 'message', contact: contactName });
    }
    
    addSystemMessage(`📞 ${currentAction === 'call' ? 'Calling' : 'Messaging'}: ${contactName}`);
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('BraillAI Web Interface Loaded');
    
    loadContacts();
    loadAllProfiles();
    
    const savedProfile = localStorage.getItem('braillai_profile');
    if (savedProfile) {
        userProfile = JSON.parse(savedProfile);
        updateGreeting();
    }
    
    const savedConfig = localStorage.getItem('braillai_config');
    if (savedConfig) {
        currentConfig = JSON.parse(savedConfig);
        const form = document.getElementById('config-form');
        if (form && currentConfig) {
            document.getElementById('gemini-key').value = currentConfig.gemini_key || '';
            document.getElementById('mobilerun-key').value = currentConfig.mobilerun_key || '';
            document.getElementById('device-id').value = currentConfig.device_id || '';
        }
    }
    
    const largeFontEnabled = localStorage.getItem('largeFont') === 'true';
    if (largeFontEnabled) {
        document.body.classList.add('large-font');
    }
    
    setTimeout(() => {
        announceScreen('welcome-screen');
    }, 1000);
    
    window.onclick = function(event) {
        const contactModal = document.getElementById('contact-modal');
        const actionModal = document.getElementById('action-modal');
        const profileSwitcherModal = document.getElementById('profile-switcher-modal');
        
        if (event.target === contactModal) {
            closeContactModal();
        }
        if (event.target === actionModal) {
            closeActionModal();
        }
        if (event.target === profileSwitcherModal) {
            closeProfileSwitcher();
        }
    };
});

const style = document.createElement('style');
style.textContent = `
@keyframes slideOutRight {
    to {
        opacity: 0;
        transform: translateX(100px);
    }
}
`;
document.head.appendChild(style);

// Text Size Toggle Function
function toggleTextSize() {
    const body = document.body;
    const isLargeFont = body.classList.contains('large-font');
    
    if (isLargeFont) {
        body.classList.remove('large-font');
        localStorage.setItem('largeFont', 'false');
        showNotification('Normal text size', 'info');
    } else {
        body.classList.add('large-font');
        localStorage.setItem('largeFont', 'true');
        showNotification('Large text size enabled', 'success');
    }
}
