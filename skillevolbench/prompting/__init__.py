"""Prompt assembly (Part 6).

* :class:`PromptBuilder` -- assembles the runtime ``instruction.md`` from
                            the original instruction + retrieval / trajectory /
                            history sections + the freeze hint.
* ``templates/``         -- (future) jinja2 templates if the inlined string
                            literals grow too big.
"""

from skillevolbench.prompting.prompt_builder import PromptBuilder

__all__ = ["PromptBuilder"]
