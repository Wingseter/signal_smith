"""
LangGraph-based AI Agent Coordinator

Orchestrates multiple AI agents for comprehensive stock analysis:
- Gemini: Real-time news analysis
- ChatGPT: Quant analysis and trading logic
- Claude: Fundamental analysis of financial reports
- ML: Chart patterns and volume analysis
"""

from typing import TypedDict, Annotated, Sequence
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.gemini_agent import GeminiNewsAgent
from app.agents.chatgpt_agent import ChatGPTQuantAgent
from app.agents.claude_agent import ClaudeFundamentalAgent
from app.agents.ml_agent import MLTechnicalAgent


class AgentState(TypedDict):
    """State shared between agents."""
    symbol: str
    messages: Annotated[Sequence[BaseMessage], "Messages exchanged between agents"]
    news_analysis: dict | None
    quant_analysis: dict | None
    fundamental_analysis: dict | None
    technical_analysis: dict | None
    final_recommendation: dict | None
    error: str | None


class AgentCoordinator:
    """Coordinates multiple AI agents using LangGraph."""

    def __init__(self):
        self.gemini_agent = GeminiNewsAgent()
        self.chatgpt_agent = ChatGPTQuantAgent()
        self.claude_agent = ClaudeFundamentalAgent()
        self.ml_agent = MLTechnicalAgent()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes for each agent
        workflow.add_node("news_analysis", self._run_news_analysis)
        workflow.add_node("quant_analysis", self._run_quant_analysis)
        workflow.add_node("fundamental_analysis", self._run_fundamental_analysis)
        workflow.add_node("technical_analysis", self._run_technical_analysis)
        workflow.add_node("synthesize", self._synthesize_results)

        # Set entry point
        workflow.set_entry_point("news_analysis")

        # Add parallel edges (all analyses run in parallel)
        workflow.add_edge("news_analysis", "quant_analysis")
        workflow.add_edge("quant_analysis", "fundamental_analysis")
        workflow.add_edge("fundamental_analysis", "technical_analysis")
        workflow.add_edge("technical_analysis", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    async def _run_news_analysis(self, state: AgentState) -> AgentState:
        """Run Gemini news analysis."""
        try:
            result = await self.gemini_agent.analyze(state["symbol"])
            state["news_analysis"] = result
            state["messages"] = list(state["messages"]) + [
                AIMessage(content=f"News Analysis: {json.dumps(result)}", name="gemini")
            ]
        except Exception as e:
            state["error"] = f"News analysis error: {str(e)}"
        return state

    async def _run_quant_analysis(self, state: AgentState) -> AgentState:
        """Run ChatGPT quant analysis."""
        try:
            result = await self.chatgpt_agent.analyze(state["symbol"])
            state["quant_analysis"] = result
            state["messages"] = list(state["messages"]) + [
                AIMessage(content=f"Quant Analysis: {json.dumps(result)}", name="chatgpt")
            ]
        except Exception as e:
            state["error"] = f"Quant analysis error: {str(e)}"
        return state

    async def _run_fundamental_analysis(self, state: AgentState) -> AgentState:
        """Run Claude fundamental analysis."""
        try:
            result = await self.claude_agent.analyze(state["symbol"])
            state["fundamental_analysis"] = result
            state["messages"] = list(state["messages"]) + [
                AIMessage(content=f"Fundamental Analysis: {json.dumps(result)}", name="claude")
            ]
        except Exception as e:
            state["error"] = f"Fundamental analysis error: {str(e)}"
        return state

    async def _run_technical_analysis(self, state: AgentState) -> AgentState:
        """Run ML technical analysis."""
        try:
            result = await self.ml_agent.analyze(state["symbol"])
            state["technical_analysis"] = result
            state["messages"] = list(state["messages"]) + [
                AIMessage(content=f"Technical Analysis: {json.dumps(result)}", name="ml")
            ]
        except Exception as e:
            state["error"] = f"Technical analysis error: {str(e)}"
        return state

    async def _synthesize_results(self, state: AgentState) -> AgentState:
        """Synthesize all analysis results into final recommendation."""
        scores = []
        analyses = []

        if state.get("news_analysis"):
            if state["news_analysis"].get("score") is not None:
                scores.append(state["news_analysis"]["score"])
            analyses.append(("news", state["news_analysis"]))

        if state.get("quant_analysis"):
            if state["quant_analysis"].get("score") is not None:
                scores.append(state["quant_analysis"]["score"])
            analyses.append(("quant", state["quant_analysis"]))

        if state.get("fundamental_analysis"):
            if state["fundamental_analysis"].get("score") is not None:
                scores.append(state["fundamental_analysis"]["score"])
            analyses.append(("fundamental", state["fundamental_analysis"]))

        if state.get("technical_analysis"):
            if state["technical_analysis"].get("score") is not None:
                scores.append(state["technical_analysis"]["score"])
            analyses.append(("technical", state["technical_analysis"]))

        # Calculate weighted average score
        overall_score = sum(scores) / len(scores) if scores else 0

        # Determine recommendation
        if overall_score > 30:
            recommendation = "buy"
        elif overall_score < -30:
            recommendation = "sell"
        else:
            recommendation = "hold"

        state["final_recommendation"] = {
            "symbol": state["symbol"],
            "overall_score": overall_score,
            "recommendation": recommendation,
            "timestamp": datetime.utcnow().isoformat(),
            "analyses_count": len(analyses),
            "confidence": min(100, len(analyses) * 25),  # 25% confidence per analysis
        }

        return state

    async def run_analysis(self, symbol: str) -> dict:
        """Run full analysis pipeline for a symbol."""
        initial_state: AgentState = {
            "symbol": symbol,
            "messages": [HumanMessage(content=f"Analyze stock: {symbol}")],
            "news_analysis": None,
            "quant_analysis": None,
            "fundamental_analysis": None,
            "technical_analysis": None,
            "final_recommendation": None,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)

        return {
            "symbol": symbol,
            "news_analysis": final_state.get("news_analysis"),
            "quant_analysis": final_state.get("quant_analysis"),
            "fundamental_analysis": final_state.get("fundamental_analysis"),
            "technical_analysis": final_state.get("technical_analysis"),
            "final_recommendation": final_state.get("final_recommendation"),
            "error": final_state.get("error"),
        }


# Singleton instance
coordinator = AgentCoordinator()


async def analyze_stock(symbol: str) -> dict:
    """Convenience function to analyze a stock."""
    return await coordinator.run_analysis(symbol)
