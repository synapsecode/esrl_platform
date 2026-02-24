let currentTaskId = null;
let pollInterval = null;

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

const examples = {
    photosynthesis: `# Photosynthesis

Photosynthesis is the process by which plants convert light energy into chemical energy.

## Key Components:
- Chlorophyll: Green pigment that captures light
- Carbon Dioxide (CO2): Absorbed from air
- Water (H2O): Absorbed from soil
- Sunlight: Energy source

## Chemical Equation:
6CO2 + 6H2O + Light Energy → C6H12O6 + 6O2

## Two Main Stages:
1. Light-dependent reactions (in thylakoids)
2. Light-independent reactions (Calvin cycle)

## Importance:
- Produces oxygen for atmosphere
- Creates glucose for plant energy
- Foundation of food chains`,

    stack: `# Stack Data Structure

A **stack** is a linear data structure following LIFO (Last In, First Out).

## Core Operations:
- **push(x)**: Insert element x on top - O(1)
- **pop()**: Remove top element - O(1)
- **top()/peek()**: View top without removing - O(1)
- **isEmpty()**: Check if empty - O(1)

## Key Characteristics:
- Access only at ONE end (the top)
- No random middle access
- Simple and efficient

## Common Applications:
- Function call stack / recursion
- Undo/Redo systems
- Expression evaluation (postfix/prefix)
- Parentheses matching
- Backtracking algorithms
- Depth First Search (DFS)

## Example:
Push: 10, 20, 30
Stack: [10, 20, 30] (30 is top)
Pop removes 30 first (LIFO)`,

    newton: `# Newton's Laws of Motion

Three fundamental laws describing the relationship between motion and forces.

## First Law (Inertia):
An object at rest stays at rest, and an object in motion stays in motion at constant velocity, unless acted upon by an external force.

**Example**: A ball on a table won't move until pushed.

## Second Law (F=ma):
Force equals mass times acceleration.
F = m × a

**Example**: Heavier objects require more force to accelerate.

## Third Law (Action-Reaction):
For every action, there is an equal and opposite reaction.

**Example**: When you push a wall, the wall pushes back with equal force.

## Applications:
- Rocket propulsion
- Car braking systems
- Sports physics
- Engineering design`
};

function loadExample(type) {
    document.getElementById('studyNotes').value = examples[type];
}

async function generateGame() {
    const studyNotes = document.getElementById('studyNotes').value.trim();

    if (!studyNotes) {
        alert('Please enter some study notes first!');
        return;
    }

    document.getElementById('inputSection').classList.add('hidden');
    document.getElementById('progressSection').classList.remove('hidden');
    document.getElementById('resultSection').classList.add('hidden');
    document.getElementById('errorSection').classList.add('hidden');

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ study_notes: studyNotes })
        });

        const data = await response.json();
        currentTaskId = data.task_id;

        pollStatus();

    } catch (error) {
        showError('Failed to start game generation: ' + error.message);
    }
}

async function pollStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/status/${currentTaskId}`);
        const data = await response.json();

        updateProgress(data);

        if (data.status === 'completed') {
            showResult(data);
            if (pollInterval) clearInterval(pollInterval);
        } else if (data.status === 'failed') {
            showError(data.error || 'Unknown error occurred');
            if (pollInterval) clearInterval(pollInterval);
        } else {
            if (!pollInterval) {
                pollInterval = setInterval(pollStatus, 2000);
            }
        }

    } catch (error) {
        showError('Failed to check status: ' + error.message);
        if (pollInterval) clearInterval(pollInterval);
    }
}

function updateProgress(data) {
    const status = data.status;
    const phase = data.phase || 'Processing...';

    document.getElementById('statusText').textContent = phase;

    const phases = ['phase1', 'phase2', 'phase3'];
    phases.forEach(p => {
        document.getElementById(p).classList.remove('active', 'completed');
    });

    let progress = 0;

    if (status === 'generating_design' || phase.includes('Game Design')) {
        document.getElementById('phase1').classList.add('active');
        progress = 33;
    } else if (status === 'generating_levels' || phase.includes('Level Design')) {
        document.getElementById('phase1').classList.add('completed');
        document.getElementById('phase2').classList.add('active');
        progress = 66;
    } else if (status === 'generating_code' || phase.includes('Code Generation')) {
        document.getElementById('phase1').classList.add('completed');
        document.getElementById('phase2').classList.add('completed');
        document.getElementById('phase3').classList.add('active');
        progress = 90;
    } else if (status === 'completed') {
        phases.forEach(p => {
            document.getElementById(p).classList.add('completed');
        });
        progress = 100;
    }

    document.getElementById('progressFill').style.width = progress + '%';
}

function showResult(data) {
    document.getElementById('progressSection').classList.add('hidden');
    document.getElementById('resultSection').classList.remove('hidden');

    if (data.game_design) {
        document.getElementById('gameDesignContent').textContent = data.game_design;
    }

    if (data.level_design) {
        document.getElementById('levelDesignContent').textContent = data.level_design;
    }

    if (data.code) {
        document.getElementById('codeContent').textContent = data.code;
    }
}

function showError(message) {
    document.getElementById('progressSection').classList.add('hidden');
    document.getElementById('resultSection').classList.add('hidden');
    document.getElementById('errorSection').classList.remove('hidden');
    document.getElementById('errorMessage').textContent = message;
}

async function launchGame(event) {
    if (!currentTaskId) return;

    const btn = event ? event.target : document.querySelector('.btn-launch');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '🚀 Launching...';

    try {
        const response = await fetch(`/api/launch/${currentTaskId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            showNotification('Game launched! Check your screen for the PyGame window.', 'success');
        } else {
            showNotification('Failed to launch: ' + (data.error || 'Unknown error'), 'error');
        }

    } catch (error) {
        showNotification('Failed to launch game: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

function resetForm() {
    currentTaskId = null;
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    document.getElementById('inputSection').classList.remove('hidden');
    document.getElementById('progressSection').classList.add('hidden');
    document.getElementById('resultSection').classList.add('hidden');
    document.getElementById('errorSection').classList.add('hidden');

    document.getElementById('progressFill').style.width = '0%';
}
