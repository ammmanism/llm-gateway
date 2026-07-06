"""
OmniModal CLI - Command-line interface for the unified gateway.
"""

import asyncio
import json
from pathlib import Path

import click
import structlog

# We can import from omnimodal dynamically to avoid circular references
# but since settings is at config, that's safe
from omnimodal.config import settings
from omnimodal.core.prompt_registry import PromptRegistry

logger = structlog.get_logger()


class MockResult:
    def __init__(self, content, cost_usd=0.01, latency_ms=500, providers=None):
        self.content = content
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.providers = providers or ["openai"]


class MockOmniClient:
    def __init__(self, api_key=None):
        self.api_key = api_key

    async def generate(self, prompt, modality, quality, max_cost_usd=None):
        return MockResult(
            content=f"Generated {modality} for prompt: {prompt}",
            cost_usd=0.002,
            latency_ms=250
        )

    async def transcribe(self, audio_data, language=None):
        return MockResult(
            content="Transcribed text from mock audio data",
            cost_usd=0.006,
            latency_ms=300
        )

    async def fuse(self, inputs, output, operation="fuse", duration_seconds=None):
        return MockResult(
            content=f"Fused multimodal output as {output}",
            cost_usd=0.045,
            latency_ms=1200,
            providers=["openai", "replicate"]
        )

    async def health(self):
        return {
            "status": "healthy",
            "version": "1.0.0",
            "providers": {
                "openai": {"enabled": True, "regions": ["us-east"]},
                "anthropic": {"enabled": True, "regions": ["us-west"]},
                "google": {"enabled": True, "regions": ["us-central"]}
            }
        }

    async def get_cost_report(self, days=30):
        return {
            "total_optimizations": 42,
            "cache_hits": 24,
            "model_downgrades": 18,
            "total_saved_usd": 1.24,
            "cache_hit_rate": 0.57
        }


@click.group()
@click.version_option(version=settings.version, prog_name="omni")
@click.option("--api-key", envvar="OMNI_API_KEY", help="OmniModal API key")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, api_key, verbose):
    """OmniModal CLI - One command for every AI modality."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["verbose"] = verbose

    if verbose:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(10))


@cli.command()
@click.argument("prompt")
@click.option("--modality", "-m", type=click.Choice(["text", "image", "audio", "video"]), default="text")
@click.option("--quality", "-q", type=click.Choice(["draft", "standard", "premium", "enterprise"]), default="standard")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--max-cost", type=float, help="Maximum cost in USD")
@click.pass_context
def generate(ctx, prompt, modality, quality, output, max_cost):
    """Generate content from a prompt."""
    async def _generate():
        client = MockOmniClient(api_key=ctx.obj["api_key"])

        with click.progressbar(length=1, label=f"Generating {modality}...") as bar:
            result = await client.generate(
                prompt=prompt,
                modality=modality,
                quality=quality,
                max_cost_usd=max_cost
            )
            bar.update(1)

        if output:
            Path(output).write_bytes(result.content if isinstance(result.content, bytes) else result.content.encode())
            click.echo(f"Success: Saved to {output}")
        else:
            click.echo(result.content)

        click.echo(f"Cost: ${result.cost_usd:.4f} | Latency: {result.latency_ms}ms")

    asyncio.run(_generate())


@cli.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--language", "-l", help="Language code (e.g., en, es)")
@click.option("--output", "-o", type=click.Path(), help="Output JSON file")
@click.pass_context
def transcribe(ctx, audio_file, language, output):
    """Transcribe audio to text."""
    async def _transcribe():
        client = MockOmniClient(api_key=ctx.obj["api_key"])

        with open(audio_file, "rb") as f:
            audio_data = f.read()

        click.echo("Transcribing...")
        result = await client.transcribe(audio_data, language=language)

        output_data = {
            "text": result.content,
            "provider": "openai",
            "cost": result.cost_usd
        }

        if output:
            Path(output).write_text(json.dumps(output_data, indent=2))
            click.echo(f"Success: Saved to {output}")
        else:
            click.echo(result.content)

    asyncio.run(_transcribe())


@cli.command()
@click.option("--input", "-i", multiple=True, help="Inputs in format type:content")
@click.option("--output-modality", "-o", type=click.Choice(["text", "image", "audio", "video", "multimodal"]), required=True)
@click.option("--operation", default="fuse")
@click.option("--duration", type=int, help="Duration in seconds (for video/audio)")
@click.pass_context
def fuse(ctx, input, output_modality, operation, duration):
    """Fuse multiple modalities into one output."""
    async def _fuse():
        client = MockOmniClient(api_key=ctx.obj["api_key"])

        inputs = []
        for item in input:
            if ":" not in item:
                raise click.BadParameter(f"Input must be in format type:content, got {item}")
            type_, content = item.split(":", 1)
            inputs.append({"type": type_, "content": content})

        click.echo(f"Fusing {len(inputs)} inputs into {output_modality}...")

        result = await client.fuse(
            inputs=inputs,
            output=output_modality,
            operation=operation,
            duration_seconds=duration
        )

        click.echo("Fusion complete!")
        click.echo(f"Providers used: {', '.join(result.providers)}")

    asyncio.run(_fuse())


@cli.command()
@click.option("--provider", "-p", help="Check specific provider")
@click.pass_context
def health(ctx, provider):
    """Check system health."""
    async def _health():
        client = MockOmniClient()
        status = await client.health()

        click.echo(f"OmniModal v{status['version']}")
        click.echo(f"Status: {status['status']}")

        for name, info in status.get("providers", {}).items():
            icon = "ENABLED" if info["enabled"] else "DISABLED"
            click.echo(f"  [{icon}] {name}: {', '.join(info['regions'])}")

    asyncio.run(_health())


@cli.command()
@click.option("--days", default=30, help="Days to analyze")
@click.pass_context
def costs(ctx, days):
    """Show cost savings report."""
    async def _costs():
        client = MockOmniClient(api_key=ctx.obj["api_key"])
        report = await client.get_cost_report(days=days)

        click.echo(f"Cost Report (Last {days} days)")
        click.echo(f"Total Optimizations: {report['total_optimizations']}")
        click.echo(f"Cache Hits: {report['cache_hits']}")
        click.echo(f"Model Downgrades: {report['model_downgrades']}")
        click.echo(f"Total Saved: ${report['total_saved_usd']:.2f}")
        click.echo(f"Cache Hit Rate: {report['cache_hit_rate']:.1%}")

    asyncio.run(_costs())


@cli.group()
def prompt():
    """Manage prompt templates (Phase 2)."""
    pass


@prompt.command()
@click.argument("name")
@click.argument("description")
@click.argument("initial_prompt")
@click.option("--variables", "-v", multiple=True, help="Template variables")
@click.pass_context
def create(ctx, name, description, initial_prompt, variables):
    """Create a new prompt template."""
    registry = PromptRegistry(storage_path=settings.core.prompt_storage_path)
    tmpl = registry.create_template(
        name=name,
        description=description,
        initial_prompt=initial_prompt,
        variables=list(variables)
    )
    click.echo(f"Created prompt template: {tmpl.name} (v{tmpl.active_version_id[:8]})")


@prompt.command()
@click.argument("name")
@click.argument("new_prompt")
@click.option("--variables", "-v", multiple=True)
@click.pass_context
def update(ctx, name, new_prompt, variables):
    """Create new version of a prompt."""
    registry = PromptRegistry(storage_path=settings.core.prompt_storage_path)
    version = registry.create_version(
        template_name=name,
        new_prompt=new_prompt,
        variables=list(variables) or None
    )
    click.echo(f"Created version {version.id[:8]} for {name}")


@prompt.command()
@click.argument("name")
@click.option("--steps", default=1, type=int)
@click.pass_context
def rollback(ctx, name, steps):
    """Rollback to previous prompt version."""
    registry = PromptRegistry(storage_path=settings.core.prompt_storage_path)
    version = registry.rollback(name, steps=steps)
    click.echo(f"Rolled back {name} to version {version.id[:8]}")


@prompt.command()
@click.argument("name")
@click.pass_context
def list_versions(ctx, name):
    """List all versions of a prompt."""
    registry = PromptRegistry(storage_path=settings.core.prompt_storage_path)
    tmpl = registry.templates.get(name)
    if not tmpl:
        click.echo(f"Template {name} not found")
        return
    for i, v in enumerate(tmpl.versions):
        marker = " [ACTIVE]" if v.id == tmpl.active_version_id else ""
        click.echo(f"  [{i}] {v.id[:8]} - created {v.created_at}{marker}")
        click.echo(f"       content: {v.content[:60]}...")


@cli.command()
@click.pass_context
def carbon(ctx):
    """Show carbon footprint report."""
    async def _carbon():
        from omnimodal.core.green_ai import CarbonTracker
        tracker = CarbonTracker(default_region=settings.core.carbon_default_region)

        # Estimate a sample request
        est = tracker.estimate("gpt-4o", 100, 50)
        tracker.track(est)

        report = tracker.get_report()
        click.echo("Carbon Footprint Report")
        click.echo("=" * 40)
        click.echo(f"Total CO2: {report['total_co2_kg']} kg")
        click.echo(f"Total Energy: {report['total_energy_kwh']} kWh")
        click.echo(f"Equivalent Car KM: {report['equivalent_car_km']}")
        click.echo(f"Equivalent Tree Hours: {report['equivalent_tree_hours']}")
        click.echo("\nRecommendations:")
        for rec in report["recommendations"]:
            click.echo(f"  - {rec}")

    asyncio.run(_carbon())


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
