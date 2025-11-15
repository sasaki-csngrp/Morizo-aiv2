"""
ResponseFormatter: Formats final responses using LLM.

This component handles formatting execution results into natural language responses.
"""

from typing import Optional, Dict, Any
from services.llm_service import LLMService
from config.loggers import GenericLogger


class ResponseFormatter:
    """Formats final responses using LLM."""
    
    def __init__(self):
        self.logger = GenericLogger("core", "response_formatter")
        self.llm_service = LLMService()
    
    async def format(self, execution_results: dict, sse_session_id: str = None) -> tuple[str, Optional[Dict[str, Any]]]:
        """Format execution results into natural language response."""
        try:
            # Use LLM service to format the response
            response, menu_data = await self.llm_service.format_response(execution_results, sse_session_id)
            self.logger.debug(f"🔍 [ResponseFormatter] Menu data received: {menu_data is not None}")
            if menu_data:
                self.logger.debug(f"📊 [ResponseFormatter] Menu data size: {len(str(menu_data))} characters")
            return response, menu_data
        except Exception as e:
            logger = GenericLogger("core", "response_formatter")
            logger.error(f"Response formatting failed: {str(e)}")
            return f"タスクが完了しましたが、レスポンスの生成に失敗しました: {str(e)}", None

