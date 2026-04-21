import 'package:flutter/material.dart';

class IconTile extends StatelessWidget {
  final IconData icon;
  final Color bg;
  final Color color;
  final double size;
  final double iconSize;
  final double radius;

  const IconTile({
    super.key,
    required this.icon,
    required this.bg,
    required this.color,
    this.size = 38,
    this.iconSize = 18,
    this.radius = 10,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(radius),
      ),
      child: Icon(icon, size: iconSize, color: color),
    );
  }
}
