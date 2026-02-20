<?php
/**
 * Refresh endpoint - fetches latest data from the EA Flood Monitoring API
 * and updates the CSV files. Called by the frontend "Refresh Data" button.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: https://tawriver.watch');

$dataDir = __DIR__ . '/data';
$apiBase = 'https://environment.data.gov.uk/flood-monitoring';

// Rate limiting: minimum 5 minutes between refreshes
$rateLimitFile = $dataDir . '/.last_refresh';
$minInterval = 300;
if (file_exists($rateLimitFile)) {
    $lastRefresh = (int)file_get_contents($rateLimitFile);
    $elapsed = time() - $lastRefresh;
    if ($elapsed < $minInterval) {
        http_response_code(429);
        echo json_encode([
            'success' => false,
            'error' => 'Too many requests',
            'retry_after' => $minInterval - $elapsed
        ]);
        exit;
    }
}
file_put_contents($rateLimitFile, (string)time());

// Station definitions matching our CSV structure
$stations = [
    // Level stations
    ['id' => '50149', 'label' => 'Sticklepath', 'type' => 'level', 'measureId' => '50149-level-stage-i-15_min-m', 'file' => 'level_50149_sticklepath.csv'],
    ['id' => '50119', 'label' => 'Taw Bridge', 'type' => 'level', 'measureId' => '50119-level-stage-i-15_min-m', 'file' => 'level_50119_taw_bridge.csv'],
    ['id' => '50132', 'label' => 'Newnham Bridge', 'type' => 'level', 'measureId' => '50132-level-stage-i-15_min-m', 'file' => 'level_50132_newnham_bridge.csv'],
    ['id' => '50140', 'label' => 'Umberleigh', 'type' => 'level', 'measureId' => '50140-level-stage-i-15_min-m', 'file' => 'level_50140_umberleigh.csv'],
    ['id' => '50198', 'label' => 'Barnstaple (Tidal)', 'type' => 'tidal', 'measureId' => '50198-level-tidal_level-i-15_min-mAOD', 'file' => 'level_50198_barnstaple_(tidal).csv'],
    // River Mole tributary stations
    ['id' => '50135', 'label' => 'North Molton', 'type' => 'level', 'measureId' => '50135-level-stage-i-15_min-m', 'file' => 'level_50135_north_molton.csv'],
    ['id' => '50153', 'label' => 'Mole Mills', 'type' => 'level', 'measureId' => '50153-level-stage-i-15_min-m', 'file' => 'level_50153_mole_mills.csv'],
    ['id' => '50115', 'label' => 'Woodleigh', 'type' => 'level', 'measureId' => '50115-level-stage-i-15_min-m', 'file' => 'level_50115_woodleigh.csv'],
    // Little Dart River tributary station
    ['id' => '50125', 'label' => 'Chulmleigh', 'type' => 'level', 'measureId' => '50125-level-stage-i-15_min-m', 'file' => 'level_50125_chulmleigh.csv'],
    // River Yeo tributary stations
    ['id' => '50151', 'label' => 'Lapford', 'type' => 'level', 'measureId' => '50151-level-stage-i-15_min-m', 'file' => 'level_50151_lapford.csv'],
    ['id' => '50114', 'label' => 'Collard Bridge', 'type' => 'level', 'measureId' => '50114-level-stage-i-15_min-m', 'file' => 'level_50114_collard_bridge.csv'],
    // Rainfall stations - East of Taw
    ['id' => '50199', 'label' => 'Lapford Bowerthy', 'type' => 'rainfall', 'measureId' => '50199-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_50199.csv'],
    ['id' => 'E85220', 'label' => 'Molland Sindercombe', 'type' => 'rainfall', 'measureId' => 'E85220-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_E85220.csv'],
    ['id' => 'E84360', 'label' => 'Crediton Knowle', 'type' => 'rainfall', 'measureId' => 'E84360-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_E84360.csv'],
    ['id' => '45183', 'label' => 'Kinsford Gate', 'type' => 'rainfall', 'measureId' => '45183-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_45183.csv'],
    // Rainfall stations - West of Taw
    ['id' => '50103', 'label' => 'Allisland', 'type' => 'rainfall', 'measureId' => '50103-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_50103.csv'],
    ['id' => '50194', 'label' => 'Kenwith Castle', 'type' => 'rainfall', 'measureId' => '50194-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_50194.csv'],
    ['id' => 'E82120', 'label' => 'Bratton Fleming Haxton', 'type' => 'rainfall', 'measureId' => 'E82120-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_E82120.csv'],
    ['id' => '47158', 'label' => 'Halwill', 'type' => 'rainfall', 'measureId' => '47158-rainfall-tipping_bucket_raingauge-t-15_min-mm', 'file' => 'rainfall_47158.csv'],
];

$results = [];
$updated = 0;

foreach ($stations as $station) {
    $stationResult = ['id' => $station['id'], 'label' => $station['label'], 'status' => 'ok', 'new_readings' => 0];

    try {
        // Read existing CSV to get existing timestamps and find the latest one
        $csvFile = $dataDir . '/' . $station['file'];
        $existingTimes = [];
        $existingLines = [];
        $latestTime = null;

        if (file_exists($csvFile)) {
            $handle = fopen($csvFile, 'r');
            $header = fgetcsv($handle);
            while (($row = fgetcsv($handle)) !== false) {
                if (count($row) >= 2) {
                    $existingTimes[$row[0]] = true;
                    $existingLines[] = $row;
                    if ($latestTime === null || strcmp($row[0], $latestTime) > 0) {
                        $latestTime = $row[0];
                    }
                }
            }
            fclose($handle);
        }

        // Determine date range to fetch
        $now = new DateTime('now', new DateTimeZone('UTC'));
        $items = [];

        if ($latestTime) {
            $lastDate = new DateTime($latestTime, new DateTimeZone('UTC'));
            $gapDays = (int)$now->diff($lastDate)->days;

            if ($gapDays <= 5) {
                // Small gap: single request with since parameter
                $url = $apiBase . '/id/measures/' . $station['measureId'] . '/readings?since=' . urlencode($latestTime) . '&_sorted&_limit=10000';
                $ctx = stream_context_create(['http' => ['timeout' => 60, 'header' => "Accept: application/json\r\n"]]);
                $response = file_get_contents($url, false, $ctx);
                if ($response !== false) {
                    $data = json_decode($response, true);
                    $items = $data['items'] ?? [];
                }
            } else {
                // Large gap: fetch in 28-day chunks from last known date to now
                $chunkEnd = clone $now;
                $chunkDays = 28;
                $startLimit = clone $lastDate;

                while ($chunkEnd > $startLimit) {
                    $chunkStart = clone $chunkEnd;
                    $chunkStart->modify("-{$chunkDays} days");
                    if ($chunkStart < $startLimit) {
                        $chunkStart = clone $startLimit;
                    }

                    $url = $apiBase . '/id/measures/' . $station['measureId'] . '/readings?startdate=' . $chunkStart->format('Y-m-d') . '&enddate=' . $chunkEnd->format('Y-m-d') . '&_sorted&_limit=100000';
                    $ctx = stream_context_create(['http' => ['timeout' => 60, 'header' => "Accept: application/json\r\n"]]);
                    $response = file_get_contents($url, false, $ctx);

                    if ($response !== false) {
                        $data = json_decode($response, true);
                        $chunkItems = $data['items'] ?? [];
                        $items = array_merge($items, $chunkItems);
                    }

                    $chunkEnd = clone $chunkStart;
                    $chunkEnd->modify('-1 day');
                    usleep(300000); // 300ms delay between chunks
                }
            }
        } else {
            // No existing data: fetch last 28 days as a starting point
            $startDate = clone $now;
            $startDate->modify('-28 days');
            $url = $apiBase . '/id/measures/' . $station['measureId'] . '/readings?startdate=' . $startDate->format('Y-m-d') . '&enddate=' . $now->format('Y-m-d') . '&_sorted&_limit=100000';
            $ctx = stream_context_create(['http' => ['timeout' => 60, 'header' => "Accept: application/json\r\n"]]);
            $response = file_get_contents($url, false, $ctx);
            if ($response !== false) {
                $data = json_decode($response, true);
                $items = $data['items'] ?? [];
            }
        }

        if (empty($items) && $latestTime) {
            $stationResult['status'] = 'no_new_data';
            $results[] = $stationResult;
            continue;
        }

        // Add new readings
        $unit = $station['type'] === 'rainfall' ? 'mm' : ($station['type'] === 'tidal' ? 'mAOD' : 'm');
        $newCount = 0;

        foreach ($items as $item) {
            $dt = $item['dateTime'] ?? '';
            $val = $item['value'] ?? '';
            if ($dt && $val !== '' && !isset($existingTimes[$dt])) {
                $existingLines[] = [$dt, $val, $unit, $station['id'], $station['label']];
                $existingTimes[$dt] = true;
                $newCount++;
            }
        }

        if ($newCount > 0) {
            // Sort by dateTime
            usort($existingLines, function($a, $b) {
                return strcmp($a[0], $b[0]);
            });

            // Write back
            $handle = fopen($csvFile, 'w');
            fputcsv($handle, ['dateTime', 'value', 'unit', 'station_id', 'station_label']);
            foreach ($existingLines as $line) {
                fputcsv($handle, $line);
            }
            fclose($handle);
            $updated++;
        }

        $stationResult['new_readings'] = $newCount;
        $stationResult['total_readings'] = count($existingLines);

    } catch (Exception $e) {
        $stationResult['status'] = 'error';
        $stationResult['message'] = $e->getMessage();
    }

    $results[] = $stationResult;
}

echo json_encode([
    'success' => true,
    'timestamp' => date('c'),
    'stations_updated' => $updated,
    'details' => $results
], JSON_PRETTY_PRINT);
