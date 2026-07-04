from app.core.rate_limiter import get_redis

async def inc_metric(name: str, labels: dict[str, str] | None = None, amount: int = 1) -> None:
    """Increment a metric in Redis."""
    redis = get_redis()
    label_str = ""
    if labels:
        label_parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = "{" + ",".join(label_parts) + "}"
    key = f"metric:{name}{label_str}"
    await redis.incrby(key, amount)

async def get_all_metrics() -> str:
    """Format all metrics from Redis in Prometheus text format."""
    redis = get_redis()
    lines = []
    
    # Queue depth is dynamic, compute it
    queue_depth = await redis.zcard("notification:queue")
    lines.append("# HELP queue_depth Current depth of the notification queue")
    lines.append("# TYPE queue_depth gauge")
    lines.append(f"queue_depth {queue_depth}")
    
    keys = await redis.keys("metric:*")
    if keys:
        values = await redis.mget(keys)
        # Sort keys for consistent output
        kv_pairs = sorted(zip(keys, values), key=lambda x: x[0])
        
        last_base_name = ""
        for key, value in kv_pairs:
            # key is like 'metric:notifications_total{channel="email",status="sent"}'
            metric_full = key[7:]  # strip 'metric:'
            base_name = metric_full.split("{")[0] if "{" in metric_full else metric_full
            
            if base_name != last_base_name:
                lines.append(f"# TYPE {base_name} counter")
                last_base_name = base_name
                
            lines.append(f"{metric_full} {value}")
            
    return "\n".join(lines) + "\n"
