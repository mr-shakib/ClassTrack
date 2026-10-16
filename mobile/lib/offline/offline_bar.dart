import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/client.dart';
import '../theme.dart';

/// "When it was saved", on Dhaka's clock: "09:12", or "15 Oct, 21:04" before today.
String savedLabel(DateTime saved) {
  final dhaka = saved.toUtc().add(const Duration(hours: 6));
  final today = DateTime.now().toUtc().add(const Duration(hours: 6));
  final sameDay = dhaka.year == today.year && dhaka.month == today.month && dhaka.day == today.day;
  return sameDay ? DateFormat('HH:mm').format(dhaka) : DateFormat('d MMM, HH:mm').format(dhaka);
}

/// A slim line above the tabs while what is on screen was saved earlier,
/// because there is no signal to ask again.
class OfflineBar extends StatelessWidget {
  const OfflineBar({super.key, required this.api});
  final Api api;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<DateTime?>(
      valueListenable: api.offline,
      builder: (context, saved, _) {
        if (saved == null) return const SizedBox.shrink();
        final p = context.palette;
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: p.subtle,
            border: Border(top: BorderSide(color: p.line)),
          ),
          child: Row(
            children: [
              Icon(Icons.cloud_off_rounded, size: 18, color: p.inkSoft),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Offline · showing what was saved at ${savedLabel(saved)}',
                  style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: p.inkSoft),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
