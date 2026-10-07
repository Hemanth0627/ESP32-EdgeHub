from ai_tools import get_device_status, set_gpio


print("========================================")
print("ESP32 EdgeHub Tool Test")
print("========================================")

print()
print("Testing device status...")
print(get_device_status())

print()
print("Testing GPIO 2 ON...")
print(set_gpio(2, "on"))

print()
print("Testing GPIO 2 OFF...")
print(set_gpio(2, "off"))

print()
print("========================================")
print("Test completed")
print("========================================")