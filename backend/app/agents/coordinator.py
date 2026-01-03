"""
LangGraph-based AI Agent Coordinator

Orchestrates multiple AI agents for comprehensive stock analysis:
- Gemini: Real-time news analysis
- ChatGPT: Quant analysis and trading logic
- Claude: Fundamental analysis of financial reports
- ML: Chart patterns and volume analysis

Enhanced with:
- Parallel execution for independent analyses
- Real data integration from external services
- Weighted scoring based on agent confidence
- Automatic signal generation
"""

import asyncio
from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.gemini_agent import GeminiNewsAgent
from app.agents.chatgpt_agent import ChatGPTQuantAgent
from app.agents.claude_agent import ClaudeFundamentalAgent
from app.agents.ml_agent import MLTechnicalAgent
from app.core.database import async_session_maker
from app.models import StockAnalysis, TradingSignal


class AgentState(TypedDict):
    """State shared between agents."""
    symbol: str
    messages: Annotated[Sequence[BaseMessage], "Messages exchanged between agents"]
    # Input data
    price_data: Optional[List[dict]]
    news_data: Optional[List[dict]]
    financial_data: Optional[dict]
    company_info: Optional[dict]
    # Analysis results
    news_analysis: Optional[dict]
    quant_analysis: Optional[dict]
    fundamental_analysis: Optional[dict]
    technical_analysis: Optional[dict]
    # Final output
    final_recommendation: Optional[dict]
    trading_signal: Optional[dict]
    error: Optional[str]


class AgentCoordinator:
    """Coordinates multiple AI agents using LangGraph with parallel execution."""

    # Weight factors for each agent (sum = 1.0)
    AGENT_WEIGHTS = {
        "news": 0.15,       # Gemini - news sentiment
        "quant": 0.30,      # ChatGPT - quantitative analysis
        "fundamental": 0.30, # Claude - fundamental analysis
        "technical": 0.25,   # ML - technical analysis
    }

    def __init__(self):
        self.gemini_agent = GeminiNewsAgent()
        self.chatgpt_agent = ChatGPTQuantAgent()
        self.claude_agent = ClaudeFundamentalAgent()
        self.ml_agent = MLTechnicalAgent()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with parallel execution."""
        workflow = StateGraph(AgentState)

        # Add nodes for each agent
        workflow.add_node("parallel_analysis", self._run_parallel_analysis)
        workflow.add_node("synthesize", self._synthesize_results)
        workflow.add_node("generate_signal", self._generate_signal)

        # Set entry point
        workflow.set_entry_point("parallel_analysis")

        # Sequential flow after parallel execution
        workflow.add_edge("parallel_analysis", "synthesize")
        workflow.add_edge("synthesize", "generate_signal")
        workflow.add_edge("generate_signal", END)

        return workflow.compile()

    async def _run_parallel_analysis(self, state: AgentState) -> AgentState:
        """Run all analyses in parallel for efficiency."""
        symbol = state["symbol"]
        price_data = state.get("price_data")
        news_data = state.get("news_data")
        financial_data = state.get("financial_data")
        company_info = state.get("company_info")

        # Create tasks for parallel execution
        tasks = [
            self._run_news_analysis(symbol, news_data, price_data),
            self._run_quant_analysis(symbol, price_data),
            self._run_fundamental_analysis(symbol, financial_data, company_info),
            self._run_technical_analysis(symbol, price_data),
        ]

        # Execute all analyses in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        news_result, quant_result, fundamental_result, technical_result = results

        # Handle exceptions
        if isinstance(news_result, Exception):
            state["error"] = f"News analysis error: {str(news_result)}"
            news_result = None
        if isinstance(quant_result, Exception):
            state["error"] = f"Quant analysis error: {str(quant_result)}"
            quant_result = None
        if isinstance(fundamental_result, Exception):
            state["error"] = f"Fundamental analysis error: {str(fundamental_result)}"
            fundamental_result = None
        if isinstance(technical_result, Exception):
            state["error"] = f"Technical analysis error: {str(technical_result)}"
            technical_result = None

        state["news_analysis"] = news_result
        state["quant_analysis"] = quant_result
        state["fundamental_analysis"] = fundamental_result
        state["technical_analysis"] = technical_result

        # Add messages for tracking
        messages = list(state.get("messages", []))
        if news_result:
            messages.append(AIMessage(
                content=f"News Analysis: {json.dumps(news_result, ensure_ascii=False)[:500]}",
                name="gemini"
            ))
        if quant_result:
            messages.append(AIMessage(
                content=f"Quant Analysis: {json.dumps(quant_result, ensure_ascii=False)[:500]}",
                name="chatgpt"
            ))
        if fundamental_result:
            messages.append(AIMessage(
                content=f"Fundamental Analysis: {json.dumps(fundamental_result, ensure_ascii=False)[:500]}",
                name="claude"
            ))
        if technical_result:
            messages.append(AIMessage(
                content=f"Technical Analysis: {json.dumps(technical_result, ensure_ascii=False)[:500]}",
                name="ml"
            ))
        state["messages"] = messages

        return state

    async def _run_news_analysis(
        self,
        symbol: str,
        news_data: Optional[List[dict]],
        price_data: Optional[List[dict]],
    ) -> dict:
        """Run Gemini news analysis."""
        price_context = None
        if price_data and len(price_data) > 0:
            latest = price_data[0]
            price_context = {
                "current_price": latest.get("close", 0),
                "change": latest.get("change", 0),
                "change_rate": latest.get("change_rate", 0),
                "volume": latest.get("volume", 0),
            }
        return await self.gemini_agent.analyze(symbol, news_data, price_context)

    async def _run_quant_analysis(
        self,
        symbol: str,
        price_data: Optional[List[dict]],
    ) -> dict:
        """Run ChatGPT quant analysis."""
        return await self.chatgpt_agent.analyze(symbol, price_data)

    async def _run_fundamental_analysis(
        self,
        symbol: str,
        financial_data: Optional[dict],
        company_info: Optional[dict],
    ) -> dict:
        """Run Claude fundamental analysis."""
        return await self.claude_agent.analyze(symbol, financial_data, company_info)

    async def _run_technical_analysis(
        self,
        symbol: str,
        price_data: Optional[List[dict]],
    ) -> dict:
        """Run ML technical analysis."""
        return await self.ml_agent.analyze(symbol, price_data)

    async def _synthesize_results(self, state: AgentState) -> AgentState:
        """Synthesize all analysis results into final recommendation with weighted scoring."""
        analyses = []
        weighted_scores = []
        total_weight = 0

        # Collect valid analyses with their weights
        if state.get("news_analysis") and state["news_analysis"].get("score") is not None:
            score = state["news_analysis"]["score"]
            confidence = state["news_analysis"].get("confidence", 50) / 100
            weight = self.AGENT_WEIGHTS["news"] * confidence
            weighted_scores.append(score * weight)
            total_weight += weight
            analyses.append(("news", state["news_analysis"]))

        if state.get("quant_analysis") and state["quant_analysis"].get("score") is not None:
            score = state["quant_analysis"]["score"]
            confidence = state["quant_analysis"].get("confidence", 50) / 100
            weight = self.AGENT_WEIGHTS["quant"] * confidence
            weighted_scores.append(score * weight)
            total_weight += weight
            analyses.append(("quant", state["quant_analysis"]))

        if state.get("fundamental_analysis") and state["fundamental_analysis"].get("score") is not None:
            score = state["fundamental_analysis"]["score"]
            confidence = state["fundamental_analysis"].get("confidence", 50) / 100
            weight = self.AGENT_WEIGHTS["fundamental"] * confidence
            weighted_scores.append(score * weight)
            total_weight += weight
            analyses.append(("fundamental", state["fundamental_analysis"]))

        if state.get("technical_analysis") and state["technical_analysis"].get("score") is not None:
            score = state["technical_analysis"]["score"]
            confidence = state["technical_analysis"].get("confidence", 50) / 100
            weight = self.AGENT_WEIGHTS["technical"] * confidence
            weighted_scores.append(score * weight)
            total_weight += weight
            analyses.append(("technical", state["technical_analysis"]))

        # Calculate weighted average score
        if total_weight > 0:
            overall_score = sum(weighted_scores) / total_weight
        else:
            overall_score = 0

        # Determine recommendation based on score thresholds
        if overall_score >= 40:
            recommendation = "strong_buy"
            signal_strength = min(100, overall_score + 20)
        elif overall_score >= 20:
            recommendation = "buy"
            signal_strength = overall_score + 10
        elif overall_score <= -40:
            recommendation = "strong_sell"
            signal_strength = min(100, abs(overall_score) + 20)
        elif overall_score <= -20:
            recommendation = "sell"
            signal_strength = abs(overall_score) + 10
        else:
            recommendation = "hold"
            signal_strength = 50 - abs(overall_score)

        # Calculate confidence based on number of successful analyses
        analysis_confidence = (len(analyses) / 4) * 100

        # Aggregate key points from all analyses
        key_points = []
        risks = []

        for analysis_type, analysis in analyses:
            if analysis.get("summary"):
                key_points.append(f"[{analysis_type}] {analysis['summary'][:100]}")
            if analysis.get("key_risks"):
                risks.extend(analysis["key_risks"][:2])
            if analysis.get("negative_factors"):
                risks.extend(analysis["negative_factors"][:2])

        state["final_recommendation"] = {
            "symbol": state["symbol"],
            "overall_score": round(overall_score, 2),
            "recommendation": recommendation,
            "signal_strength": round(signal_strength, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "analyses_count": len(analyses),
            "confidence": round(analysis_confidence, 2),
            "agent_scores": {
                "news": state.get("news_analysis", {}).get("score"),
                "quant": state.get("quant_analysis", {}).get("score"),
                "fundamental": state.get("fundamental_analysis", {}).get("score"),
                "technical": state.get("technical_analysis", {}).get("score"),
            },
            "key_points": key_points[:5],
            "risks": list(set(risks))[:5],
        }

        return state

    async def _generate_signal(self, state: AgentState) -> AgentState:
        """Generate trading signal based on analysis."""
        recommendation = state.get("final_recommendation", {})

        if not recommendation:
            return state

        rec = recommendation.get("recommendation", "hold")
        strength = recommendation.get("signal_strength", 0)
        score = recommendation.get("overall_score", 0)

        # Only generate signals for actionable recommendations
        if rec in ["strong_buy", "buy", "strong_sell", "sell"] and strength >= 50:
            signal_type = "buy" if rec in ["strong_buy", "buy"] else "sell"

            # Get target price from quant analysis if available
            quant = state.get("quant_analysis", {})
            target_price = None
            stop_loss = None

            if quant.get("entry_point"):
                try:
                    target_price = float(str(quant["entry_point"]).replace(",", "").replace("원", ""))
                except (ValueError, TypeError):
                    pass

            if quant.get("exit_point"):
                try:
                    stop_loss = float(str(quant["exit_point"]).replace(",", "").replace("원", ""))
                except (ValueError, TypeError):
                    pass

            # Build reason from key points
            reasons = recommendation.get("key_points", [])
            reason = " | ".join(reasons[:3]) if reasons else f"{rec.upper()} signal with {strength:.0f}% strength"

            state["trading_signal"] = {
                "symbol": state["symbol"],
                "signal_type": signal_type,
                "strength": strength / 100,  # Normalize to 0-1
                "source_agent": "coordinator",
                "reason": reason[:500],
                "target_price": target_price,
                "stop_loss": stop_loss,
                "recommendation": rec,
                "overall_score": score,
                "created_at": datetime.utcnow().isoformat(),
            }

        return state

    async def run_analysis(
        self,
        symbol: str,
        price_data: Optional[List[dict]] = None,
        news_data: Optional[List[dict]] = None,
        financial_data: Optional[dict] = None,
        company_info: Optional[dict] = None,
        save_to_db: bool = True,
    ) -> dict:
        """
        Run full analysis pipeline for a symbol.

        Args:
            symbol: Stock symbol to analyze
            price_data: Historical price data
            news_data: Recent news articles
            financial_data: Financial statement data
            company_info: Company information
            save_to_db: Whether to save results to database

        Returns:
            Complete analysis results
        """
        initial_state: AgentState = {
            "symbol": symbol,
            "messages": [HumanMessage(content=f"Analyze stock: {symbol}")],
            "price_data": price_data,
            "news_data": news_data,
            "financial_data": financial_data,
            "company_info": company_info,
            "news_analysis": None,
            "quant_analysis": None,
            "fundamental_analysis": None,
            "technical_analysis": None,
            "final_recommendation": None,
            "trading_signal": None,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)

        # Optionally save to database
        if save_to_db:
            await self._save_analyses(final_state)

        return {
            "symbol": symbol,
            "news_analysis": final_state.get("news_analysis"),
            "quant_analysis": final_state.get("quant_analysis"),
            "fundamental_analysis": final_state.get("fundamental_analysis"),
            "technical_analysis": final_state.get("technical_analysis"),
            "final_recommendation": final_state.get("final_recommendation"),
            "trading_signal": final_state.get("trading_signal"),
            "error": final_state.get("error"),
        }

    async def _save_analyses(self, state: AgentState):
        """Save analysis results to database."""
        symbol = state["symbol"]

        async with async_session_maker() as session:
            # Save each analysis type
            analyses_to_save = [
                ("news", "gemini", state.get("news_analysis")),
                ("quant", "chatgpt", state.get("quant_analysis")),
                ("fundamental", "claude", state.get("fundamental_analysis")),
                ("technical", "ml", state.get("technical_analysis")),
            ]

            for analysis_type, agent_name, analysis in analyses_to_save:
                if analysis and not analysis.get("error"):
                    db_analysis = StockAnalysis(
                        symbol=symbol,
                        analysis_type=analysis_type,
                        agent_name=agent_name,
                        summary=analysis.get("summary", "")[:1000],
                        score=Decimal(str(analysis.get("score", 0))) if analysis.get("score") is not None else None,
                        recommendation=analysis.get("recommendation"),
                        raw_data=analysis,
                    )
                    session.add(db_analysis)

            # Save trading signal if generated
            if state.get("trading_signal"):
                signal = state["trading_signal"]
                db_signal = TradingSignal(
                    symbol=symbol,
                    signal_type=signal["signal_type"],
                    strength=Decimal(str(signal["strength"])),
                    source_agent=signal["source_agent"],
                    reason=signal["reason"],
                    target_price=Decimal(str(signal["target_price"])) if signal.get("target_price") else None,
                    stop_loss=Decimal(str(signal["stop_loss"])) if signal.get("stop_loss") else None,
                )
                session.add(db_signal)

            await session.commit()

    async def run_quick_analysis(self, symbol: str, price_data: Optional[List[dict]] = None) -> dict:
        """
        Run a quick analysis using only technical and quant agents.

        For faster response when full analysis is not needed.
        """
        tasks = [
            self._run_quant_analysis(symbol, price_data),
            self._run_technical_analysis(symbol, price_data),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        quant_result, technical_result = results

        scores = []
        if not isinstance(quant_result, Exception) and quant_result.get("score") is not None:
            scores.append(quant_result["score"])
        if not isinstance(technical_result, Exception) and technical_result.get("score") is not None:
            scores.append(technical_result["score"])

        overall_score = sum(scores) / len(scores) if scores else 0

        if overall_score > 20:
            recommendation = "buy"
        elif overall_score < -20:
            recommendation = "sell"
        else:
            recommendation = "hold"

        return {
            "symbol": symbol,
            "quant_analysis": quant_result if not isinstance(quant_result, Exception) else {"error": str(quant_result)},
            "technical_analysis": technical_result if not isinstance(technical_result, Exception) else {"error": str(technical_result)},
            "overall_score": overall_score,
            "recommendation": recommendation,
            "analysis_type": "quick",
            "timestamp": datetime.utcnow().isoformat(),
        }


# Singleton instance
coordinator = AgentCoordinator()


async def analyze_stock(
    symbol: str,
    price_data: Optional[List[dict]] = None,
    news_data: Optional[List[dict]] = None,
    financial_data: Optional[dict] = None,
    company_info: Optional[dict] = None,
) -> dict:
    """Convenience function to analyze a stock."""
    return await coordinator.run_analysis(
        symbol=symbol,
        price_data=price_data,
        news_data=news_data,
        financial_data=financial_data,
        company_info=company_info,
    )


async def quick_analyze_stock(symbol: str, price_data: Optional[List[dict]] = None) -> dict:
    """Convenience function for quick analysis."""
    return await coordinator.run_quick_analysis(symbol, price_data)
