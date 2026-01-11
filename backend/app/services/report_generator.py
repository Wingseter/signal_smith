"""
AI Analysis Report PDF Generator
종합 분석 PDF 생성 서비스
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

import logging

logger = logging.getLogger(__name__)


class ReportType(Enum):
    STOCK_ANALYSIS = "stock_analysis"
    PORTFOLIO_REVIEW = "portfolio_review"
    MARKET_OVERVIEW = "market_overview"
    TRADING_SUMMARY = "trading_summary"
    FULL_REPORT = "full_report"


@dataclass
class StockAnalysisData:
    """Individual stock analysis data."""
    symbol: str
    name: str
    current_price: float
    price_change: float
    price_change_pct: float
    volume: int
    market_cap: float
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    dividend_yield: Optional[float]
    technical_score: float
    fundamental_score: float
    sentiment_score: float
    overall_score: float
    recommendation: str
    price_target: Optional[float]
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    analysis_summary: str = ""
    ai_insights: List[str] = field(default_factory=list)


@dataclass
class PortfolioData:
    """Portfolio summary data."""
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    cash_balance: float
    positions: List[Dict[str, Any]]
    sector_allocation: Dict[str, float]
    risk_metrics: Dict[str, float]


@dataclass
class MarketOverviewData:
    """Market overview data."""
    indices: List[Dict[str, Any]]
    sector_performance: List[Dict[str, Any]]
    top_gainers: List[Dict[str, Any]]
    top_losers: List[Dict[str, Any]]
    market_sentiment: str
    volatility_index: float
    trading_volume: int
    market_summary: str


@dataclass
class TradingSummaryData:
    """Trading activity summary."""
    period_start: datetime
    period_end: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_profit: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    trades: List[Dict[str, Any]]
    signals_generated: int
    signals_executed: int


@dataclass
class ReportConfig:
    """Report configuration."""
    report_type: ReportType
    title: str
    subtitle: str = ""
    include_charts: bool = True
    include_ai_insights: bool = True
    language: str = "ko"  # ko or en


class ReportGenerator:
    """AI Analysis Report PDF Generator."""

    # Korean text styling
    COLORS = {
        "primary": colors.HexColor("#1E40AF"),
        "secondary": colors.HexColor("#6B7280"),
        "success": colors.HexColor("#059669"),
        "danger": colors.HexColor("#DC2626"),
        "warning": colors.HexColor("#D97706"),
        "light": colors.HexColor("#F3F4F6"),
        "dark": colors.HexColor("#1F2937"),
    }

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            fontSize=24,
            leading=28,
            textColor=self.COLORS["primary"],
            spaceAfter=12,
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            fontSize=14,
            leading=18,
            textColor=self.COLORS["secondary"],
            spaceAfter=24,
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            fontSize=16,
            leading=20,
            textColor=self.COLORS["primary"],
            spaceBefore=16,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='SubSectionHeader',
            fontSize=12,
            leading=16,
            textColor=self.COLORS["dark"],
            spaceBefore=12,
            spaceAfter=6,
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='BodyText',
            fontSize=10,
            leading=14,
            textColor=self.COLORS["dark"],
            spaceAfter=8,
        ))

        self.styles.add(ParagraphStyle(
            name='InsightText',
            fontSize=10,
            leading=14,
            textColor=self.COLORS["secondary"],
            leftIndent=12,
            spaceAfter=4,
        ))

        self.styles.add(ParagraphStyle(
            name='FooterText',
            fontSize=8,
            leading=10,
            textColor=self.COLORS["secondary"],
            alignment=1,  # Center
        ))

    def generate_stock_report(
        self,
        stock_data: StockAnalysisData,
        config: ReportConfig,
    ) -> BytesIO:
        """Generate stock analysis PDF report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        story = []

        # Title section
        story.append(Paragraph(config.title, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"{stock_data.symbol} - {stock_data.name}",
            self.styles['ReportSubtitle']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['FooterText']
        ))
        story.append(Spacer(1, 12))
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=self.COLORS["light"],
        ))
        story.append(Spacer(1, 12))

        # Price overview
        story.append(Paragraph("Price Overview", self.styles['SectionHeader']))

        price_color = self.COLORS["success"] if stock_data.price_change >= 0 else self.COLORS["danger"]
        change_symbol = "+" if stock_data.price_change >= 0 else ""

        price_data = [
            ["Current Price", f"₩{stock_data.current_price:,.0f}"],
            ["Change", f"{change_symbol}₩{stock_data.price_change:,.0f} ({change_symbol}{stock_data.price_change_pct:.2f}%)"],
            ["Volume", f"{stock_data.volume:,}"],
            ["Market Cap", f"₩{stock_data.market_cap/1e12:.2f}T"],
        ]

        price_table = Table(price_data, colWidths=[120, 200])
        price_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.COLORS["dark"]),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(price_table)
        story.append(Spacer(1, 16))

        # Valuation metrics
        if any([stock_data.pe_ratio, stock_data.pb_ratio, stock_data.dividend_yield]):
            story.append(Paragraph("Valuation Metrics", self.styles['SectionHeader']))

            valuation_data = []
            if stock_data.pe_ratio:
                valuation_data.append(["P/E Ratio", f"{stock_data.pe_ratio:.2f}"])
            if stock_data.pb_ratio:
                valuation_data.append(["P/B Ratio", f"{stock_data.pb_ratio:.2f}"])
            if stock_data.dividend_yield:
                valuation_data.append(["Dividend Yield", f"{stock_data.dividend_yield:.2f}%"])

            if valuation_data:
                valuation_table = Table(valuation_data, colWidths=[120, 200])
                valuation_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
                    ('TEXTCOLOR', (0, 0), (-1, -1), self.COLORS["dark"]),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
                ]))
                story.append(valuation_table)
                story.append(Spacer(1, 16))

        # Analysis scores
        story.append(Paragraph("AI Analysis Scores", self.styles['SectionHeader']))

        score_data = [
            ["Analysis Type", "Score", "Rating"],
            ["Technical", f"{stock_data.technical_score:.1f}/100", self._get_rating(stock_data.technical_score)],
            ["Fundamental", f"{stock_data.fundamental_score:.1f}/100", self._get_rating(stock_data.fundamental_score)],
            ["Sentiment", f"{stock_data.sentiment_score:.1f}/100", self._get_rating(stock_data.sentiment_score)],
            ["Overall", f"{stock_data.overall_score:.1f}/100", self._get_rating(stock_data.overall_score)],
        ]

        score_table = Table(score_data, colWidths=[150, 100, 100])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (0, -1), self.COLORS["light"]),
            ('TEXTCOLOR', (0, 1), (-1, -1), self.COLORS["dark"]),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 16))

        # Recommendation
        story.append(Paragraph("Investment Recommendation", self.styles['SectionHeader']))

        rec_color = {
            "STRONG_BUY": self.COLORS["success"],
            "BUY": self.COLORS["success"],
            "HOLD": self.COLORS["warning"],
            "SELL": self.COLORS["danger"],
            "STRONG_SELL": self.COLORS["danger"],
        }.get(stock_data.recommendation, self.COLORS["secondary"])

        rec_text = {
            "STRONG_BUY": "Strong Buy (Highly Recommended)",
            "BUY": "Buy",
            "HOLD": "Hold",
            "SELL": "Sell",
            "STRONG_SELL": "Strong Sell (Avoid)",
        }.get(stock_data.recommendation, stock_data.recommendation)

        rec_data = [["Recommendation", rec_text]]
        if stock_data.price_target:
            rec_data.append(["Price Target", f"₩{stock_data.price_target:,.0f}"])
            upside = ((stock_data.price_target / stock_data.current_price) - 1) * 100
            rec_data.append(["Potential Upside", f"{upside:+.1f}%"])

        rec_table = Table(rec_data, colWidths=[150, 200])
        rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('TEXTCOLOR', (1, 0), (1, 0), rec_color),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(rec_table)
        story.append(Spacer(1, 16))

        # Support/Resistance levels
        if stock_data.support_levels or stock_data.resistance_levels:
            story.append(Paragraph("Key Price Levels", self.styles['SectionHeader']))

            levels_data = [["Type", "Level 1", "Level 2", "Level 3"]]

            if stock_data.support_levels:
                support_row = ["Support"] + [
                    f"₩{lvl:,.0f}" if lvl else "-"
                    for lvl in (stock_data.support_levels + [None, None, None])[:3]
                ]
                levels_data.append(support_row)

            if stock_data.resistance_levels:
                resistance_row = ["Resistance"] + [
                    f"₩{lvl:,.0f}" if lvl else "-"
                    for lvl in (stock_data.resistance_levels + [None, None, None])[:3]
                ]
                levels_data.append(resistance_row)

            levels_table = Table(levels_data, colWidths=[100, 100, 100, 100])
            levels_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 1), (0, -1), self.COLORS["light"]),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(levels_table)
            story.append(Spacer(1, 16))

        # AI Insights
        if config.include_ai_insights and stock_data.ai_insights:
            story.append(Paragraph("AI Insights", self.styles['SectionHeader']))

            for i, insight in enumerate(stock_data.ai_insights, 1):
                story.append(Paragraph(
                    f"{i}. {insight}",
                    self.styles['InsightText']
                ))

            story.append(Spacer(1, 16))

        # Analysis Summary
        if stock_data.analysis_summary:
            story.append(Paragraph("Analysis Summary", self.styles['SectionHeader']))
            story.append(Paragraph(stock_data.analysis_summary, self.styles['BodyText']))

        # Footer
        story.append(Spacer(1, 24))
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=self.COLORS["light"],
        ))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This report is generated by Signal Smith AI Analysis System. "
            "It is for informational purposes only and should not be considered as financial advice.",
            self.styles['FooterText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_portfolio_report(
        self,
        portfolio_data: PortfolioData,
        config: ReportConfig,
    ) -> BytesIO:
        """Generate portfolio review PDF report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        story = []

        # Title
        story.append(Paragraph(config.title, self.styles['ReportTitle']))
        if config.subtitle:
            story.append(Paragraph(config.subtitle, self.styles['ReportSubtitle']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['FooterText']
        ))
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 16))

        # Portfolio Summary
        story.append(Paragraph("Portfolio Summary", self.styles['SectionHeader']))

        pnl_color = self.COLORS["success"] if portfolio_data.total_pnl >= 0 else self.COLORS["danger"]
        change_symbol = "+" if portfolio_data.total_pnl >= 0 else ""

        summary_data = [
            ["Total Value", f"₩{portfolio_data.total_value:,.0f}"],
            ["Total Cost", f"₩{portfolio_data.total_cost:,.0f}"],
            ["P&L", f"{change_symbol}₩{portfolio_data.total_pnl:,.0f} ({change_symbol}{portfolio_data.total_pnl_pct:.2f}%)"],
            ["Cash Balance", f"₩{portfolio_data.cash_balance:,.0f}"],
        ]

        summary_table = Table(summary_data, colWidths=[150, 200])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 16))

        # Risk Metrics
        if portfolio_data.risk_metrics:
            story.append(Paragraph("Risk Metrics", self.styles['SectionHeader']))

            risk_data = []
            metric_names = {
                "sharpe_ratio": "Sharpe Ratio",
                "sortino_ratio": "Sortino Ratio",
                "max_drawdown": "Max Drawdown",
                "volatility": "Volatility",
                "beta": "Beta",
                "var_95": "VaR (95%)",
            }

            for key, name in metric_names.items():
                if key in portfolio_data.risk_metrics:
                    value = portfolio_data.risk_metrics[key]
                    if key in ["max_drawdown", "volatility", "var_95"]:
                        risk_data.append([name, f"{value:.2f}%"])
                    else:
                        risk_data.append([name, f"{value:.2f}"])

            if risk_data:
                risk_table = Table(risk_data, colWidths=[150, 100])
                risk_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
                ]))
                story.append(risk_table)
                story.append(Spacer(1, 16))

        # Holdings
        story.append(Paragraph("Holdings", self.styles['SectionHeader']))

        if portfolio_data.positions:
            holdings_data = [["Symbol", "Name", "Qty", "Avg Cost", "Current", "P&L", "Weight"]]

            for pos in portfolio_data.positions[:20]:  # Limit to 20
                pnl = pos.get("unrealized_pnl", 0)
                pnl_str = f"{'+'if pnl >= 0 else ''}₩{pnl:,.0f}"
                weight = pos.get("weight", 0)

                holdings_data.append([
                    pos.get("symbol", ""),
                    pos.get("name", "")[:12],
                    str(pos.get("quantity", 0)),
                    f"₩{pos.get('avg_cost', 0):,.0f}",
                    f"₩{pos.get('current_price', 0):,.0f}",
                    pnl_str,
                    f"{weight:.1f}%",
                ])

            holdings_table = Table(holdings_data, colWidths=[50, 80, 40, 70, 70, 70, 50])
            holdings_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(holdings_table)
        else:
            story.append(Paragraph("No positions", self.styles['BodyText']))

        story.append(Spacer(1, 16))

        # Sector Allocation
        if portfolio_data.sector_allocation:
            story.append(Paragraph("Sector Allocation", self.styles['SectionHeader']))

            sector_data = [["Sector", "Weight"]]
            sorted_sectors = sorted(
                portfolio_data.sector_allocation.items(),
                key=lambda x: x[1],
                reverse=True
            )

            for sector, weight in sorted_sectors[:10]:
                sector_data.append([sector, f"{weight:.1f}%"])

            sector_table = Table(sector_data, colWidths=[200, 100])
            sector_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(sector_table)

        # Footer
        story.append(Spacer(1, 24))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This report is generated by Signal Smith AI Analysis System.",
            self.styles['FooterText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_trading_report(
        self,
        trading_data: TradingSummaryData,
        config: ReportConfig,
    ) -> BytesIO:
        """Generate trading summary PDF report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        story = []

        # Title
        story.append(Paragraph(config.title, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Period: {trading_data.period_start.strftime('%Y-%m-%d')} ~ {trading_data.period_end.strftime('%Y-%m-%d')}",
            self.styles['ReportSubtitle']
        ))
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 16))

        # Trading Summary
        story.append(Paragraph("Trading Summary", self.styles['SectionHeader']))

        pnl_color = self.COLORS["success"] if trading_data.total_pnl >= 0 else self.COLORS["danger"]
        change_symbol = "+" if trading_data.total_pnl >= 0 else ""

        summary_data = [
            ["Total Trades", str(trading_data.total_trades)],
            ["Winning Trades", str(trading_data.winning_trades)],
            ["Losing Trades", str(trading_data.losing_trades)],
            ["Win Rate", f"{trading_data.win_rate:.1f}%"],
            ["Total P&L", f"{change_symbol}₩{trading_data.total_pnl:,.0f}"],
        ]

        summary_table = Table(summary_data, colWidths=[150, 150])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 16))

        # Performance Metrics
        story.append(Paragraph("Performance Metrics", self.styles['SectionHeader']))

        perf_data = [
            ["Average Profit", f"₩{trading_data.avg_profit:,.0f}"],
            ["Average Loss", f"₩{trading_data.avg_loss:,.0f}"],
            ["Largest Win", f"₩{trading_data.largest_win:,.0f}"],
            ["Largest Loss", f"₩{trading_data.largest_loss:,.0f}"],
            ["Signals Generated", str(trading_data.signals_generated)],
            ["Signals Executed", str(trading_data.signals_executed)],
        ]

        perf_table = Table(perf_data, colWidths=[150, 150])
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(perf_table)
        story.append(Spacer(1, 16))

        # Recent Trades
        if trading_data.trades:
            story.append(Paragraph("Recent Trades", self.styles['SectionHeader']))

            trades_data = [["Date", "Symbol", "Type", "Qty", "Price", "P&L"]]

            for trade in trading_data.trades[:15]:  # Limit to 15
                pnl = trade.get("pnl", 0)
                pnl_str = f"{'+'if pnl >= 0 else ''}₩{pnl:,.0f}"
                trade_date = trade.get("date", "")
                if isinstance(trade_date, datetime):
                    trade_date = trade_date.strftime("%m/%d")

                trades_data.append([
                    trade_date,
                    trade.get("symbol", ""),
                    trade.get("type", ""),
                    str(trade.get("quantity", 0)),
                    f"₩{trade.get('price', 0):,.0f}",
                    pnl_str,
                ])

            trades_table = Table(trades_data, colWidths=[60, 70, 50, 50, 80, 80])
            trades_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(trades_table)

        # Footer
        story.append(Spacer(1, 24))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This report is generated by Signal Smith AI Analysis System.",
            self.styles['FooterText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_market_report(
        self,
        market_data: MarketOverviewData,
        config: ReportConfig,
    ) -> BytesIO:
        """Generate market overview PDF report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        story = []

        # Title
        story.append(Paragraph(config.title, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['ReportSubtitle']
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 16))

        # Market Indices
        if market_data.indices:
            story.append(Paragraph("Market Indices", self.styles['SectionHeader']))

            indices_data = [["Index", "Value", "Change", "% Change"]]
            for idx in market_data.indices:
                change = idx.get("change", 0)
                change_pct = idx.get("change_pct", 0)
                change_str = f"{'+'if change >= 0 else ''}{change:,.2f}"
                pct_str = f"{'+'if change_pct >= 0 else ''}{change_pct:.2f}%"

                indices_data.append([
                    idx.get("name", ""),
                    f"{idx.get('value', 0):,.2f}",
                    change_str,
                    pct_str,
                ])

            indices_table = Table(indices_data, colWidths=[120, 100, 80, 80])
            indices_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(indices_table)
            story.append(Spacer(1, 16))

        # Market Sentiment
        story.append(Paragraph("Market Overview", self.styles['SectionHeader']))

        sentiment_color = {
            "BULLISH": self.COLORS["success"],
            "BEARISH": self.COLORS["danger"],
            "NEUTRAL": self.COLORS["warning"],
        }.get(market_data.market_sentiment, self.COLORS["secondary"])

        overview_data = [
            ["Market Sentiment", market_data.market_sentiment],
            ["Volatility Index", f"{market_data.volatility_index:.2f}"],
            ["Trading Volume", f"{market_data.trading_volume:,}"],
        ]

        overview_table = Table(overview_data, colWidths=[150, 150])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 16))

        # Sector Performance
        if market_data.sector_performance:
            story.append(Paragraph("Sector Performance", self.styles['SectionHeader']))

            sector_data = [["Sector", "1D", "1W", "1M"]]
            for sector in market_data.sector_performance[:10]:
                sector_data.append([
                    sector.get("name", ""),
                    f"{sector.get('return_1d', 0):+.2f}%",
                    f"{sector.get('return_1w', 0):+.2f}%",
                    f"{sector.get('return_1m', 0):+.2f}%",
                ])

            sector_table = Table(sector_data, colWidths=[150, 70, 70, 70])
            sector_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(sector_table)
            story.append(Spacer(1, 16))

        # Top Gainers & Losers
        story.append(Paragraph("Top Gainers", self.styles['SubSectionHeader']))

        if market_data.top_gainers:
            gainers_data = [["Symbol", "Name", "Price", "Change"]]
            for stock in market_data.top_gainers[:5]:
                gainers_data.append([
                    stock.get("symbol", ""),
                    stock.get("name", "")[:15],
                    f"₩{stock.get('price', 0):,.0f}",
                    f"+{stock.get('change_pct', 0):.2f}%",
                ])

            gainers_table = Table(gainers_data, colWidths=[70, 130, 90, 80])
            gainers_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["success"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('TEXTCOLOR', (-1, 1), (-1, -1), self.COLORS["success"]),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(gainers_table)

        story.append(Spacer(1, 12))
        story.append(Paragraph("Top Losers", self.styles['SubSectionHeader']))

        if market_data.top_losers:
            losers_data = [["Symbol", "Name", "Price", "Change"]]
            for stock in market_data.top_losers[:5]:
                losers_data.append([
                    stock.get("symbol", ""),
                    stock.get("name", "")[:15],
                    f"₩{stock.get('price', 0):,.0f}",
                    f"{stock.get('change_pct', 0):.2f}%",
                ])

            losers_table = Table(losers_data, colWidths=[70, 130, 90, 80])
            losers_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["danger"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('TEXTCOLOR', (-1, 1), (-1, -1), self.COLORS["danger"]),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ]))
            story.append(losers_table)

        # Market Summary
        if market_data.market_summary:
            story.append(Spacer(1, 16))
            story.append(Paragraph("Market Summary", self.styles['SectionHeader']))
            story.append(Paragraph(market_data.market_summary, self.styles['BodyText']))

        # Footer
        story.append(Spacer(1, 24))
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["light"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This report is generated by Signal Smith AI Analysis System.",
            self.styles['FooterText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def _get_rating(self, score: float) -> str:
        """Get rating text from score."""
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Average"
        elif score >= 20:
            return "Below Average"
        else:
            return "Poor"
