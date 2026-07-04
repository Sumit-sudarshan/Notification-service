import uuid
from typing import Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import UndefinedError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.template import Template

# Using StrictUndefined ensures that if a variable is missing, Jinja raises an exception
# rather than silently rendering an empty string.
jinja_env = Environment(undefined=StrictUndefined)

async def render_template(
    session: AsyncSession,
    variables: dict[str, Any],
    template_id: uuid.UUID | None = None,
    inline_body: str | None = None,
    inline_subject: str | None = None,
) -> dict[str, str]:
    """
    Renders a notification template. Supports both DB-stored templates (via template_id)
    and ad-hoc inline templates (via inline_body).
    
    Returns a dict with 'body' and optionally 'subject'.
    """
    if template_id:
        template = await session.get(Template, template_id)
        if not template:
            raise ValidationError(f"Template with id {template_id} not found")
        
        # Validate required variables
        missing = [var for var in template.required_variables if var not in variables]
        if missing:
            raise ValidationError(f"Missing required template variables: {', '.join(missing)}")
        
        body_tmpl_str = template.body_template
        subject_tmpl_str = template.subject_template
    elif inline_body:
        body_tmpl_str = inline_body
        subject_tmpl_str = inline_subject
    else:
        raise ValidationError("Must provide either template_id or inline_body")

    try:
        body_template = jinja_env.from_string(body_tmpl_str)
        rendered_body = body_template.render(**variables)
        
        result = {"body": rendered_body}
        
        if subject_tmpl_str:
            subject_template = jinja_env.from_string(subject_tmpl_str)
            result["subject"] = subject_template.render(**variables)
            
        return result
    except UndefinedError as e:
        raise ValidationError(f"Template rendering failed (missing variable): {str(e)}")
    except Exception as e:
        raise ValidationError(f"Template rendering error: {str(e)}")
