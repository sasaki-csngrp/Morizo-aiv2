"""
ActionPlanner: Task planning specialist for the core layer.

This component analyzes user requests and generates executable task lists
with proper dependency resolution.
"""

import uuid
import logging
from typing import List, Dict, Any
from .models import Task, TaskStatus
from .exceptions import PlanningError
from .service_coordinator import ServiceCoordinator
from services.llm_service import LLMService
from config.loggers import GenericLogger


class ActionPlanner:
    """Plans and decomposes user requests into executable tasks."""
    
    def __init__(self):
        self.logger = GenericLogger("core", "planner")
        self.llm_service = LLMService()
        self.service_coordinator = ServiceCoordinator()
        self.service_registry = self._build_service_registry()
    
    def _build_service_registry(self) -> Dict[str, Dict[str, Any]]:
        """Build registry of available services and their methods."""
        return {
            "RecipeService": {
                "generate_menu_plan": {
                    "description": "Generate a menu plan based on available ingredients",
                    "parameters": ["ingredients", "preferences", "dietary_restrictions"]
                },
                "search_recipes_from_web": {
                    "description": "Search for recipes from web sources",
                    "parameters": ["query", "max_results"]
                },
                "search_menu_from_rag": {
                    "description": "Search for recipes using RAG",
                    "parameters": ["query", "max_results"]
                },
                "get_recipe_history": {
                    "description": "Get user's recipe history",
                    "parameters": ["user_id", "limit"]
                }
            },
            "InventoryService": {
                "add_inventory": {
                    "description": "Add items to inventory",
                    "parameters": ["items", "user_id"]
                },
                "get_inventory": {
                    "description": "Get user's inventory",
                    "parameters": ["user_id"]
                },
                "get_inventory_by_name": {
                    "description": "Get inventory items by name",
                    "parameters": ["name", "user_id"]
                },
                "update_inventory_by_id": {
                    "description": "Update inventory item by ID",
                    "parameters": ["item_id", "updates", "user_id"]
                },
                "delete_inventory_by_id": {
                    "description": "Delete inventory item by ID",
                    "parameters": ["item_id", "user_id"]
                }
            },
            "SessionService": {
                "create_session": {
                    "description": "Create a new session",
                    "parameters": ["user_id", "session_data"]
                },
                "get_session": {
                    "description": "Get session information",
                    "parameters": ["session_id"]
                },
                "update_session": {
                    "description": "Update session data",
                    "parameters": ["session_id", "updates"]
                },
                "delete_session": {
                    "description": "Delete session",
                    "parameters": ["session_id"]
                }
            }
        }
    
    async def plan(self, user_request: str, user_id: str, sse_session_id: str = None) -> List[Task]:
        """
        Plan tasks based on user request.
        
        Args:
            user_request: User's natural language request
            user_id: User identifier
            sse_session_id: SSE session ID (for additional proposal context)
            
        Returns:
            List of tasks with dependencies resolved
        """
        try:
            self.logger.info(f"🎯 [PLANNER] Starting task planning for user {user_id}")
            self.logger.info(f"📝 [PLANNER] User request: '{user_request}'")
            
            # Get available tools description
            tools_description = self.service_coordinator.get_available_tools_description()
            self.logger.debug(f"🔧 [PLANNER] Retrieved {len(tools_description)} available tools")
            
            # Use LLM to decompose the request into tasks
            # Phase 1F: sse_session_idを渡す（追加提案の場合）
            task_descriptions = await self.llm_service.decompose_tasks(
                user_request, tools_description, user_id, sse_session_id
            )
            self.logger.debug(f"🤖 [PLANNER] LLM generated {len(task_descriptions)} task descriptions")
            
            # Convert descriptions to Task objects
            tasks = self._create_tasks_from_descriptions(task_descriptions, user_id)
            self.logger.debug(f"📋 [PLANNER] Created {len(tasks)} tasks from descriptions")
            
            # Log task details
            for i, task in enumerate(tasks, 1):
                self.logger.debug(f"  {i}. {task.service}.{task.method} (id: {task.id}, deps: {task.dependencies})")
                self.logger.debug(f"     Parameters: {task.parameters}")
            
            # Resolve dependencies
            tasks = self._resolve_dependencies(tasks)
            self.logger.debug(f"🔗 [PLANNER] Dependencies resolved for {len(tasks)} tasks")
            
            # Log final task structure
            for i, task in enumerate(tasks, 1):
                self.logger.debug(f"  {i}. {task.service}.{task.method} (id: {task.id}, resolved_deps: {task.dependencies})")
            
            self.logger.info(f"✅ [PLANNER] Task planning completed successfully")
            return tasks
            
        except Exception as e:
            self.logger.error(f"❌ [PLANNER] Task planning failed: {str(e)}")
            raise PlanningError(f"Failed to plan tasks: {str(e)}")
    
    def _create_tasks_from_descriptions(self, descriptions: List[Dict], user_id: str) -> List[Task]:
        """Convert task descriptions to Task objects."""
        tasks = []
        
        for desc in descriptions:
            # LLMが生成したtask1, task2形式のIDをそのまま使用
            task_id = desc.get("id", f"task{len(tasks)+1}")
            service = desc.get("service")
            method = desc.get("method")
            parameters = desc.get("parameters", {})
            
            # 常に実際のuser_idで上書き（LLMが生成した"user123"等を置き換え）
            parameters["user_id"] = user_id
            
            task = Task(
                id=task_id,
                service=service,
                method=method,
                parameters=parameters,
                dependencies=desc.get("dependencies", [])
            )
            tasks.append(task)
        
        return tasks
    
    def _resolve_dependencies(self, tasks: List[Task]) -> List[Task]:
        """Resolve task dependencies and update dependency IDs."""
        # task1, task2形式のIDをそのまま使用するため、依存関係解決は不要
        # LLMが既に正しい依存関係を生成している
        return tasks
