.DEFAULT_GOAL := help
.PHONY: help init build up start stop down restart rebuild rebuild-clean shell root status logs run gpu opengl cuda gazebo lidar rviz colcon rosdep topics doctor config
ROBO := bash ./scripts/robo.sh
export CMD

help: ## Показать команды
	@awk 'BEGIN {FS = ":.*## "; printf "Команды учебного контейнера:\n"} /^[a-zA-Z_-]+:.*## / {printf "  make %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
init: ## Создать .env и папку ros2_ws/src
	@$(ROBO) init
build: ## Собрать образ с кэшем Docker
	@$(ROBO) build
up: ## Собрать при необходимости и запустить контейнер с GUI/GPU
	@$(ROBO) up
start: ## То же, что make up
	@$(ROBO) up
stop: ## Остановить контейнер, сохранив файлы
	@$(ROBO) stop
down: ## Удалить контейнер, сохранив исходники и домашний том
	@$(ROBO) down
restart: ## Пересоздать контейнер и обновить доступ к текущему экрану
	@$(ROBO) restart
rebuild: ## Пересобрать образ с кэшем и пересоздать контейнер
	@$(ROBO) rebuild
rebuild-clean: ## Полностью пересобрать образ без кэша и пересоздать контейнер
	@$(ROBO) rebuild-clean
shell: ## Открыть Bash внутри контейнера от student
	@$(ROBO) shell
root: ## Открыть Bash внутри контейнера от root
	@$(ROBO) root
status: ## Состояние контейнера
	@$(ROBO) status
logs: ## Следить за журналом основного процесса (Ctrl+C — выход)
	@$(ROBO) logs
run: ## Выполнить команду: make run CMD='ros2 topic list'
	@$(ROBO) run
gpu: ## Показать nvidia-smi внутри контейнера
	@$(ROBO) exec nvidia-smi
opengl: ## Проверить, что OpenGL использует NVIDIA
	@$(ROBO) opengl
cuda: ## Запустить вычислительный тест CUDA
	@$(ROBO) exec python3 /work/gpu-check/cuda_smoke.py
gazebo: ## Открыть пустой мир Gazebo Fortress
	@$(ROBO) gazebo
lidar: ## Открыть пример Gazebo visualize_lidar.sdf
	@$(ROBO) lidar
rviz: ## Открыть RViz2
	@$(ROBO) rviz
colcon: ## Собрать ROS-пакеты из ros2_ws/src
	@$(ROBO) exec colcon build --symlink-install
rosdep: ## Установить зависимости пакетов из ros2_ws/src в контейнер
	@$(ROBO) run-rosdep
topics: ## Показать ROS-топики
	@$(ROBO) exec ros2 topic list
doctor: ## Проверить хост, GPU, Compose и запущенный контейнер
	@$(ROBO) doctor
config: ## Проверить синтаксис Compose
	@$(ROBO) config
