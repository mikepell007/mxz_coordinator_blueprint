# Dynamic Temperature Controls Enhancement

This document explains how to implement dynamic temperature controls in Home Assistant UI cards that adapt based on whether a room uses single or dual setpoint configuration.

## Understanding the Configuration

The MXZ Coordinator blueprint supports two types of room configurations:

1. **Single Setpoint Rooms**: Use `input_number.room_target` for a single target temperature
2. **Dual Setpoint Rooms**: Use both `input_number.room_heat_to` and `input_number.room_cool_to` for separate heating and cooling targets

## Implementation Approach: Conditional Templates

The most straightforward approach is to use conditional templates in your UI card that detect the room's configuration and show appropriate controls.

### Sample Implementation

Here's how to create a dynamic UI card using conditional templates:

```yaml
# Example of a dynamic climate card with conditional temperature controls
type: custom:mushroom-climate-card
entity: climate.virtual_office_climate
show_temperature_control: true
collapsible_controls: true
temperature_controls:
  # Single setpoint control (shown when target is configured but heat_to/cool_to are empty)
  - type: temperature
    entity: input_number.mxz_home_office_target
    name: Target Temperature
    visible: "{{ states('input_number.mxz_home_office_target') != '' and (states('input_number.mxz_home_office_heat_to') == '' or states('input_number.mxz_home_office_heat_to') is not defined) and (states('input_number.mxz_home_office_cool_to') == '' or states('input_number.mxz_home_office_cool_to') is not defined) }}"
  
  # Dual setpoint controls (shown when both heat_to and cool_to are configured)
  - type: temperature
    entity: input_number.mxz_home_office_heat_to
    name: Heat To
    visible: "{{ states('input_number.mxz_home_office_heat_to') != '' }}"
    
  - type: temperature
    entity: input_number.mxz_home_office_cool_to
    name: Cool To  
    visible: "{{ states('input_number.mxz_home_office_cool_to') != '' }}"

tap_action:
  action: call-service
  service: input_boolean.toggle
  target:
    entity_id: input_boolean.mxz_home_office_enable
```

### Alternative Approach with More Precise Logic

For more precise detection, you can use a more complex conditional check:

```yaml
# More precise implementation that checks for actual configuration
type: custom:mushroom-climate-card
entity: climate.virtual_office_climate
show_temperature_control: true
collapsible_controls: true
temperature_controls:
  # Single setpoint control
  - type: temperature
    entity: input_number.mxz_home_office_target
    name: Target Temperature
    visible: >
      {{ 
        (states('input_number.mxz_home_office_target') != '' and 
         states('input_number.mxz_home_office_target') != 'unknown' and
         states('input_number.mxz_home_office_target') != 'unavailable') and
        ((states('input_number.mxz_home_office_heat_to') == '' or states('input_number.mxz_home_office_heat_to') is not defined) and
         (states('input_number.mxz_home_office_cool_to') == '' or states('input_number.mxz_home_office_cool_to') is not defined))
      }}
  
  # Dual setpoint controls
  - type: temperature
    entity: input_number.mxz_home_office_heat_to
    name: Heat To
    visible: >
      {{ 
        (states('input_number.mxz_home_office_heat_to') != '' and 
         states('input_number.mxz_home_office_heat_to') != 'unknown' and
         states('input_number.mxz_home_office_heat_to') != 'unavailable')
      }}
    
  - type: temperature
    entity: input_number.mxz_home_office_cool_to
    name: Cool To  
    visible: >
      {{ 
        (states('input_number.mxz_home_office_cool_to') != '' and 
         states('input_number.mxz_home_office_cool_to') != 'unknown' and
         states('input_number.mxz_home_office_cool_to') != 'unavailable')
      }}

tap_action:
  action: call-service
  service: input_boolean.toggle
  target:
    entity_id: input_boolean.mxz_home_office_enable
```

### Implementation Steps

1. **Identify Your Room Configuration**: Determine which rooms use single setpoint vs dual setpoint
2. **Create the Template Logic**: Use the conditional logic above to detect configuration
3. **Test with Different Room Types**: Verify controls appear correctly for both room types
4. **Adjust Visibility Conditions**: Fine-tune conditions based on your specific setup

## Blueprint Integration

The blueprint handles the detection internally by checking:
1. If `room_target` is configured → Single setpoint mode
2. If both `room_heat_to` and `room_cool_to` are configured → Dual setpoint mode
3. If only one of heat_to or cool_to is configured → Invalid configuration

## Best Practices

1. **Consistent UI Design**: Maintain consistent styling across single and dual setpoint displays
2. **Clear Visual Indicators**: Show which mode a room is using in the UI
3. **Responsive Controls**: Ensure controls update immediately when room configuration changes
4. **Error Handling**: Gracefully handle misconfigured rooms
5. **Testing**: Test with both single and dual setpoint rooms to ensure proper visibility

## Testing

To test the dynamic controls:
1. Configure a room as single setpoint and verify only one control appears
2. Convert the same room to dual setpoint and verify both controls appear
3. Ensure the blueprint behavior remains unchanged regardless of UI display
4. Test with mixed room configurations in the same automation