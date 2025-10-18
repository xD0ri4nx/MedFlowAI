#!/bin/bash

echo "Testing /schedule_appointment endpoint..."
echo "=========================================="
echo ""

curl -X POST "http://localhost:8000/schedule_appointment" \
  -H "Content-Type: application/json" \
  -d @test_schedule.json

echo ""
echo ""
echo "=========================================="
echo "Check your server console for the email!"
