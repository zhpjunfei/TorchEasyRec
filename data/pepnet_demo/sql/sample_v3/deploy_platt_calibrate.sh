#!/bin/bash
# 一键部署 platt_calibrate.py 和 platt_inject_into_export.py 到 DLC worker
# 用法: bash deploy_platt_calibrate.sh <dlc-worker-ip>

set -e

DLC_IP="${1:?Usage: $0 <dlc-worker-ip>}"

echo "=== Deploying platt calibration tools to ${DLC_IP} ==="

# 1. 打包修改后的文件
cd "$(dirname "$0")/../../.."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TMPDIR="/tmp/platt_deploy_${TIMESTAMP}"
mkdir -p "$TMPDIR/tzrec/tools"

cp tzrec/tools/platt_calibrate.py "$TMPDIR/tzrec/tools/"
cp tzrec/tools/platt_inject_into_export.py "$TMPDIR/tzrec/tools/"

echo "Packed files:"
ls -la "$TMPDIR/tzrec/tools/"

# 2. 上传到 DLC worker (需要配置 SSH key)
echo "Uploading to root@${DLC_IP}..."
scp -r "$TMPDIR/tzrec/tools/" "root@${DLC_IP}:/opt/conda/lib/python3.11/site-packages/tzrec/tools/"

echo "Verifying upload..."
ssh "root@${DLC_IP}" "ls -la /opt/conda/lib/python3.11/site-packages/tzrec/tools/platt_calibrate.py"
ssh "root@${DLC_IP}" "md5sum /opt/conda/lib/python3.11/site-packages/tzrec/tools/platt_calibrate.py"

# 3. 清理临时文件
rm -rf "$TMPDIR"

echo "=== Deployment complete! ==="
echo "Next: Resubmit your DLC training job."
