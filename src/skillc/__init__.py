"""skillc -- the Skill Achievability Compiler.

Decides whether the goal of an agent skill (SKILL.md / agent markdown / a
formal achievability pack) is achievable in a given capability context.
Sound for refutation (Coq-proved core, proof/SkillAchievability.v);
deliberately incomplete for achievement.
"""
from .checker import Checker, Verdict, check
from .evaluate import evaluate, load_corpus
from .frontend.markdown import CompileResult, compile_file, compile_markdown
from .pack import Capability, Pack, PackError, validate_pack
from .profiles import Profile, builtin_profiles, load_profile

__version__ = "0.1.0"

__all__ = [
    "Checker", "Verdict", "check",
    "Pack", "Capability", "PackError", "validate_pack",
    "Profile", "load_profile", "builtin_profiles",
    "CompileResult", "compile_markdown", "compile_file",
    "evaluate", "load_corpus",
    "__version__",
]
