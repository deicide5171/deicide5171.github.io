---
title: "Flutter를 이용한 앱 개발 #2"
date: "2024-07-03 00:21:38 +0900"
categories: my project
---
# Flutter를 이용한 앱 개발

- MaterialApp
  - Example
    return MaterialApp(
      return home: Text("")
    );
  - MaterialApp() : Widget, Google Material에서 제공하는 스타일 사용 가능, Custom Style도 이걸로 활용
  - CupertinoXXX() : Widget, iOS 스타일 사용 가능

- 기본 Widget
  - Text("{문자열}")
  - Image.asset('{이미지 경로}') : /assets/images 폴더, Example : assets/images/xxx.png
    - pubspec.yaml : 앱 만들때, 필요한 자료(이미지, 라이브러리? 등등 정의)를 정리한 파일
  - Icon(Icons.star)
  - Container() or SizedBox()
    - Examples1 : Container(width: 50, height: 50, color: Colors.red) // 숫자 단위는 LP, 50LP == 1.2cm
    - Examples2
      Center(
        child: Container(width: 50, height: 50, color: Colors.red),
      )

- Layout
  - Scaffold() : 상중하로 나눈 레이아웃, 기본 앱 스타일
    - appBar
    - body
    - bottomNavigationBar
  - Row
  - Column

[jekyll-docs]: https://jekyllrb.com/docs/home
[jekyll-gh]:   https://github.com/jekyll/jekyll
[jekyll-talk]: https://talk.jekyllrb.com/