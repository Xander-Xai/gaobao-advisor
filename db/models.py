"""
ORM 模型 — 5 张核心表（移植自上游项目）
"""
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint, Index, DateTime
from sqlalchemy.orm import relationship
from db.database import Base
import datetime


class School(Base):
    """院校表"""
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    province = Column(String(20), nullable=False)
    city = Column(String(30), nullable=False, default="")
    level = Column(String(20), nullable=False, default="普通")       # 985/211/双一流/普通
    school_type = Column(String(20), nullable=False, default="综合")  # 综合/理工/医药/师范/财经
    ranking = Column(Integer, nullable=True)                          # 软科排名
    is_985 = Column(Integer, default=0)
    is_211 = Column(Integer, default=0)
    is_double_first_class = Column(Integer, default=0)
    website = Column(String(200), nullable=True)
    description = Column(String(500), nullable=True)

    admission_scores = relationship("AdmissionScore", back_populates="school")
    enrollment_plans = relationship("EnrollmentPlan", back_populates="school")
    subject_rankings = relationship("SubjectRanking", back_populates="school")

    __table_args__ = (
        Index("ix_schools_province", "province"),
        Index("ix_schools_level", "level"),
    )

    def __repr__(self):
        return f"<School({self.name}, {self.level})>"


class Major(Base):
    """专业表"""
    __tablename__ = "majors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), nullable=False)         # 学科门类: 工学/理学/医学
    sub_category = Column(String(50), nullable=True)      # 专业类: 计算机类/电子信息类
    employment_rate = Column(Float, nullable=True)        # 就业率 0-1
    avg_salary = Column(Float, nullable=True)             # 毕业五年平均月薪（元）
    median_salary = Column(Float, nullable=True)          # 薪资中位数
    salary_range = Column(Text, nullable=True)            # JSON: {"low": x, "high": y}
    top_industries = Column(Text, nullable=True)          # JSON 数组
    employment_locations = Column(Text, nullable=True)    # JSON 数组
    postgraduate_rate = Column(Float, nullable=True)      # 考研比例
    overseas_rate = Column(Float, nullable=True)          # 出国比例
    description = Column(Text, nullable=True)
    job_directions = Column(Text, nullable=True)          # JSON 数组
    is_hot = Column(Integer, default=0)
    education_level = Column(String(10), nullable=True, default="本科")  # 本科/专科

    admission_scores = relationship("AdmissionScore", back_populates="major")
    enrollment_plans = relationship("EnrollmentPlan", back_populates="major")

    __table_args__ = (
        Index("ix_majors_category", "category"),
    )

    def __repr__(self):
        return f"<Major({self.name}, {self.category})>"


class AdmissionScore(Base):
    """录取分数线表"""
    __tablename__ = "admission_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    major_id = Column(Integer, ForeignKey("majors.id"), nullable=True)  # null = 院校分数线
    province = Column(String(20), nullable=False)
    year = Column(Integer, nullable=False)
    batch = Column(String(20), nullable=False, default="本科一批")
    subject_type = Column(String(10), nullable=False, default="综合")  # 理工/文史/物理类/历史类
    min_score = Column(Integer, nullable=True)
    avg_score = Column(Float, nullable=True)
    max_score = Column(Integer, nullable=True)
    min_rank = Column(Integer, nullable=True)
    plan_count = Column(Integer, nullable=True)

    school = relationship("School", back_populates="admission_scores")
    major = relationship("Major", back_populates="admission_scores")

    __table_args__ = (
        UniqueConstraint("school_id", "major_id", "province", "year", "batch", "subject_type",
                         name="uq_admission_score"),
        Index("ix_adm_school_province_year", "school_id", "province", "year"),
    )

    def __repr__(self):
        return f"<AdmScore({self.school_id}, {self.province}, {self.year}, {self.min_score})>"


class EnrollmentPlan(Base):
    """招生计划表"""
    __tablename__ = "enrollment_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    major_id = Column(Integer, ForeignKey("majors.id"), nullable=False)
    province = Column(String(20), nullable=False)
    year = Column(Integer, nullable=False)
    plan_count = Column(Integer, nullable=True)
    subject_requirement = Column(String(100), nullable=True)  # 物理必选/不限
    batch = Column(String(20), nullable=True)
    duration = Column(Integer, nullable=True)                  # 学制年数
    tuition = Column(Integer, nullable=True)                   # 学费元/年

    school = relationship("School", back_populates="enrollment_plans")
    major = relationship("Major", back_populates="enrollment_plans")

    __table_args__ = (
        UniqueConstraint("school_id", "major_id", "province", "year", name="uq_enrollment_plan"),
    )


class SubjectRanking(Base):
    """学科排名表"""
    __tablename__ = "subject_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    major_category = Column(String(50), nullable=False)
    ranking_source = Column(String(50), nullable=False)
    ranking_year = Column(Integer, nullable=False)
    ranking_position = Column(Integer, nullable=True)
    grade = Column(String(10), nullable=True)  # A+/A/A-/B+/B/B-/C+/C/C-

    school = relationship("School", back_populates="subject_rankings")

    __table_args__ = (
        UniqueConstraint("school_id", "major_category", "ranking_source", "ranking_year",
                         name="uq_subject_ranking"),
    )


# ── 对话持久化（P3） ──

class Conversation(Base):
    """对话会话表 — 支持关闭页面后恢复"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    user_label = Column(String(50), nullable=True)  # 用户标签（可选）
    province = Column(String(20), nullable=True)
    score_rank = Column(String(30), nullable=True)
    subject = Column(String(50), nullable=True)
    slots_json = Column(Text, nullable=True)         # 完整 slots JSON
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc),
                        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )


class ConversationMessage(Base):
    """对话消息表"""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")


class YiFenYiDuan(Base):
    """一分一段表 — 真实位次映射"""
    __tablename__ = "yi_fen_yi_duan"

    id = Column(Integer, primary_key=True, autoincrement=True)
    province = Column(String(20), nullable=False)
    year = Column(Integer, nullable=False)
    subject_type = Column(String(10), nullable=False, default="综合")
    score = Column(Integer, nullable=False)
    cumulative_count = Column(Integer, nullable=False)  # 累计人数（位次）

    __table_args__ = (
        UniqueConstraint("province", "year", "subject_type", "score", name="uq_yi_fen_yi_duan"),
        Index("ix_yfdd_province_year", "province", "year"),
    )

    def __repr__(self):
        return f"<YiFenYiDuan({self.province}, {self.year}, {self.score}分, 位次{self.cumulative_count})>"


class Highlight(Base):
    """金句表 — 高传播力的优质回复片段"""
    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)       # 金句内容
    score = Column(Integer, default=0)            # 自评分数（0-100）
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def __repr__(self):
        return f"<Highlight({self.session_id}, score={self.score}, {self.content[:20]}...)>"


class Feedback(Base):
    """用户反馈表 — 每条AI回复的有帮助/没帮助评分"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    message_index = Column(Integer, nullable=False)  # 消息在会话中的序号
    rating = Column(String(10), nullable=False)       # "helpful" / "not_helpful"
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (
        Index("ix_feedback_session_msg", "session_id", "message_index"),
    )

    def __repr__(self):
        return f"<Feedback({self.session_id}, #{self.message_index}, {self.rating})>"

