# Jarvis Multitasking

Jarvis can now run multiple commands in parallel. Long running actions are sent
into a background task queue and you can manage them with voice commands.

## Usage
- **list tasks** – speak the status of all running tasks
- **cancel task `<id>`** – cancel a background task
- **clear queue** – cancel and remove all pending tasks
- **what's running?** – alias for **list tasks**

Tasks are automatically announced when they finish.
