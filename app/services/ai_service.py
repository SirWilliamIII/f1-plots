"""
AI Service

Handles AI prompt creation and formatting for telemetry analysis.
"""


def create_contextual_prompt(user_prompt, context):
    """Create optimized prompt with essential telemetry context for faster processing"""

    race_info = context["race_info"]
    drv1 = context["driver1"]
    drv2 = context["driver2"]
    comparison = context["comparison"]
    sectors = context["sectors"]

    # Simplified context for faster processing
    context_text = f"""
F1 TELEMETRY ANALYSIS:
{race_info['year']} {race_info['race_name']} - {race_info['session_type']}

DRIVERS:
**{drv1['name']}** ({drv1['full_name']}): {drv1['lap_time']:.3f}s, {drv1['max_speed']:.0f} km/h
**{drv2['name']}** ({drv2['full_name']}): {drv2['lap_time']:.3f}s, {drv2['max_speed']:.0f} km/h

RESULT: **{comparison['faster_driver']}** faster by {comparison['lap_time_delta']:.3f}s

SECTORS:"""

    for sector in sectors:
        context_text += f"""
Sector {sector['sector']}: {sector['faster_driver']} faster by {sector['delta']:.3f}s
- {drv1['name']}: {sector['driver1_time']:.3f}s
- {drv2['name']}: {sector['driver2_time']:.3f}s"""

    # Add key moments (simplified)
    if "plot_annotations" in context and context["plot_annotations"]:
        context_text += f"""

KEY MOMENTS:"""
        for i, annotation in enumerate(context["plot_annotations"][:3]):  # Limit to 3 most important
            context_text += f"""
- {annotation['time']}: {annotation['description']}"""

    context_text += f"""

QUESTION: {user_prompt}

Provide a concise analysis focusing on the key differences between the drivers."""

    return context_text
