import uuid
import pytest
from unittest.mock import AsyncMock

from app.core.exceptions import ValidationError
from app.services.template_service import render_template
from app.models.template import Template

@pytest.mark.asyncio
async def test_inline_template_success():
    session = AsyncMock()
    variables = {"name": "Alice", "amount": "50.00"}
    
    result = await render_template(
        session, 
        variables=variables, 
        inline_body="Hello {{name}}, you spent ${{amount}}",
        inline_subject="Update for {{name}}"
    )
    
    assert result["body"] == "Hello Alice, you spent $50.00"
    assert result["subject"] == "Update for Alice"

@pytest.mark.asyncio
async def test_inline_template_missing_var():
    session = AsyncMock()
    variables = {"name": "Alice"}
    
    with pytest.raises(ValidationError, match="Template rendering failed"):
        await render_template(
            session, 
            variables=variables, 
            inline_body="Hello {{name}}, you spent ${{amount}}"
        )

@pytest.mark.asyncio
async def test_inline_template_extra_var_ignored():
    session = AsyncMock()
    variables = {"name": "Alice", "extra": "ignored"}
    
    result = await render_template(
        session, 
        variables=variables, 
        inline_body="Hello {{name}}"
    )
    
    assert result["body"] == "Hello Alice"

@pytest.mark.asyncio
async def test_db_template_success():
    session = AsyncMock()
    tmpl_id = uuid.uuid4()
    
    mock_tmpl = Template(
        id=tmpl_id,
        body_template="Hi {{user}}",
        required_variables=["user"]
    )
    session.get.return_value = mock_tmpl
    
    result = await render_template(
        session,
        variables={"user": "Bob"},
        template_id=tmpl_id
    )
    
    assert result["body"] == "Hi Bob"

@pytest.mark.asyncio
async def test_db_template_missing_required_var():
    session = AsyncMock()
    tmpl_id = uuid.uuid4()
    
    mock_tmpl = Template(
        id=tmpl_id,
        body_template="Hi {{user}}",
        required_variables=["user"]
    )
    session.get.return_value = mock_tmpl
    
    with pytest.raises(ValidationError, match="Missing required template variables: user"):
        await render_template(
            session,
            variables={"wrong": "Bob"},
            template_id=tmpl_id
        )
