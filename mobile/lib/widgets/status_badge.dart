import 'package:flutter/material.dart';
import '../config/theme.dart';

enum BadgeKind {
  pending, approved, rejected, cancelled,
  inProgress, done, todo,
  paid, draft, calculated,
  late, present, absent,
  high, medium, low,
}

class StatusBadge extends StatelessWidget {
  final BadgeKind kind;
  final String? label;
  final bool small;

  const StatusBadge({super.key, required this.kind, this.label, this.small = false});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    Color bg;
    Color fg;
    String text;

    switch (kind) {
      case BadgeKind.pending:
        bg = sem.warningContainer; fg = sem.warning; text = 'Pending';
      case BadgeKind.approved:
        bg = sem.successContainer; fg = sem.success; text = 'Approved';
      case BadgeKind.rejected:
        bg = sem.dangerContainer; fg = sem.danger; text = 'Rejected';
      case BadgeKind.cancelled:
        bg = isDark ? const Color(0xFF1F2937) : const Color(0xFFEEF2F6);
        fg = sem.textSub; text = 'Cancelled';
      case BadgeKind.inProgress:
        bg = sem.infoContainer; fg = sem.info; text = 'In Progress';
      case BadgeKind.done:
        bg = sem.successContainer; fg = sem.success; text = 'Done';
      case BadgeKind.todo:
        bg = isDark ? const Color(0xFF1F2937) : const Color(0xFFEEF2F6);
        fg = sem.textSub; text = 'To Do';
      case BadgeKind.paid:
        bg = sem.successContainer; fg = sem.success; text = 'Paid';
      case BadgeKind.draft:
        bg = isDark ? const Color(0xFF1F2937) : const Color(0xFFEEF2F6);
        fg = sem.textSub; text = 'Draft';
      case BadgeKind.calculated:
        bg = sem.infoContainer; fg = sem.info; text = 'Calculated';
      case BadgeKind.late:
        bg = sem.warningContainer; fg = sem.warning; text = 'Late';
      case BadgeKind.present:
        bg = sem.successContainer; fg = sem.success; text = 'Present';
      case BadgeKind.absent:
        bg = sem.dangerContainer; fg = sem.danger; text = 'Absent';
      case BadgeKind.high:
        bg = sem.dangerContainer; fg = sem.danger; text = 'High';
      case BadgeKind.medium:
        bg = sem.warningContainer; fg = sem.warning; text = 'Medium';
      case BadgeKind.low:
        bg = sem.infoContainer; fg = sem.info; text = 'Low';
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: small ? 8 : 10,
        vertical: small ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label ?? text,
        style: TextStyle(
          color: fg,
          fontSize: small ? 10.5 : 11.5,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

BadgeKind statusToBadge(String status) {
  switch (status.toLowerCase()) {
    case 'pending': return BadgeKind.pending;
    case 'approved': return BadgeKind.approved;
    case 'rejected': return BadgeKind.rejected;
    case 'cancelled': return BadgeKind.cancelled;
    case 'in_progress': return BadgeKind.inProgress;
    case 'done': return BadgeKind.done;
    case 'todo': return BadgeKind.todo;
    case 'paid': return BadgeKind.paid;
    case 'draft': return BadgeKind.draft;
    case 'calculated': return BadgeKind.calculated;
    case 'late': return BadgeKind.late;
    default: return BadgeKind.pending;
  }
}
