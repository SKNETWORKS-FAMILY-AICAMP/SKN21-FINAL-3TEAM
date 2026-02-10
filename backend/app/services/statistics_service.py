"""
통계 서비스 (팀원 D 담당)

UI_UX.pdf: "Top 질의 응답 (월/주/일)", "시스템 현황 (통계, AI 정확도 리포트)"
요구사항: NF-ST-002
"""


class StatisticsService:
    """통계 서비스"""

    async def get_top_queries(self, period: str = "daily", limit: int = 10) -> list:
        """
        인기 질의 Top N 조회

        Args:
            period: 'daily' | 'weekly' | 'monthly'
            limit: 상위 N개

        Returns:
            [{"question": "...", "count": 15, "intent": "judgment", "last_asked": "..."}]
        """
        # TODO: 팀원 D 구현
        # chat_logs 테이블에서 기간별 질의 집계
        raise NotImplementedError

    async def get_dashboard_stats(self, user_id: int = None) -> dict:
        """
        대시보드 통계 카드 데이터

        Returns:
            {
                "today_queries": 24,
                "processed_meetings": 5,
                "completed_action_items": 12,
                "risk_alerts": 3
            }
        """
        # TODO: 팀원 D 구현
        raise NotImplementedError

    async def get_query_logs(
        self, page: int = 1, per_page: int = 20, filters: dict = None
    ) -> dict:
        """
        질의 로그 조회 (관리자 전용)

        UI_UX.pdf: "[추가] 질의 로그 탭 (사용자, 질문 내용, 호출된 Agent, 응답 시간)"

        Returns:
            {
                "items": [{"user", "question", "agent", "response_time", "timestamp"}],
                "total": 150,
                "page": 1
            }
        """
        # TODO: 팀원 D 구현
        raise NotImplementedError
