  # Stop the proxy
  sudo systemctl stop f1-beam-proxy

  # App still works, AI just shows offline
  curl -s http://localhost:5151/ | head -20

  # Warmup fails gracefully
  curl -s -X POST http://localhost:5151/warmup_gpu

  # To pause Beam and save costs during low-traffic periods, just:
  sudo systemctl stop f1-beam-proxy
  
  # And restart when needed:
  sudo systemctl start f1-beam-proxy
